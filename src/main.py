import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree
from urllib.parse import urlparse

DEFAULT_OUTPUT = "graph.svg"
DEFAULT_MAX_DEPTH = 3
MIN_MAX_DEPTH = 1
MAX_PACKAGE_LENGTH = 100
PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
URL_SCHEMES = ("http", "https")
IMAGE_EXTENSION = ".svg"
FORBIDDEN_FILE_CHARS = '<>:"|?*'
REQUEST_TIMEOUT = 15
HTTP_NOT_FOUND = 404
PACKAGE_BASE_TYPE = "PackageBaseAddress/3.0.0"


class NuGetError(Exception):
    """Ошибка получения данных из репозитория NuGet."""


class NotFoundError(NuGetError):
    """Запрошенный ресурс отсутствует в репозитории."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Разбирает параметры командной строки."""
    parser = argparse.ArgumentParser(
        description="Визуализатор графа зависимостей пакетов NuGet")
    parser.add_argument("-p", "--package", default=None,
                        help="имя анализируемого пакета")
    parser.add_argument("-r", "--repo", default=None,
                        help="URL-адрес репозитория или путь к файлу "
                             "тестового репозитория")
    parser.add_argument("-t", "--test-mode", action="store_true",
                        help="режим работы с тестовым репозиторием")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="имя файла с изображением графа "
                             f"(по умолчанию {DEFAULT_OUTPUT})")
    parser.add_argument("-a", "--ascii-tree", action="store_true",
                        help="вывод зависимостей в виде ASCII-дерева")
    parser.add_argument("-d", "--max-depth",
                        default=str(DEFAULT_MAX_DEPTH),
                        help="максимальная глубина анализа зависимостей "
                             f"(по умолчанию {DEFAULT_MAX_DEPTH})")
    return parser.parse_args(argv)


def validate_package(package: str | None) -> str | None:
    """Проверяет имя пакета. Возвращает текст ошибки или None."""
    if not package:
        return "не задано имя пакета (--package)"
    if len(package) > MAX_PACKAGE_LENGTH:
        return (f"имя пакета длиннее {MAX_PACKAGE_LENGTH} символов "
                "(--package)")
    if not PACKAGE_PATTERN.match(package):
        return (f"недопустимое имя пакета '{package}': разрешены "
                "латинские буквы, цифры и символы . _ - (--package)")
    return None


def validate_repo(repo: str | None, test_mode: bool) -> str | None:
    """Проверяет URL репозитория или путь к тестовому репозиторию."""
    if not repo:
        return "не задан URL-адрес или путь к репозиторию (--repo)"
    if test_mode:
        if not os.path.isfile(repo):
            return f"файл тестового репозитория '{repo}' не найден (--repo)"
        return None
    url = urlparse(repo)
    if url.scheme not in URL_SCHEMES or not url.netloc:
        return (f"некорректный URL-адрес репозитория '{repo}': ожидается "
                "адрес вида https://... (для файла укажите --test-mode)")
    return None


def validate_output(output: str) -> str | None:
    """Проверяет имя файла для изображения графа."""
    name = os.path.basename(output)
    if not name:
        return "не задано имя файла с изображением графа (--output)"
    if any(char in name for char in FORBIDDEN_FILE_CHARS):
        return (f"имя файла '{name}' содержит недопустимые символы "
                f"{FORBIDDEN_FILE_CHARS} (--output)")
    if not name.lower().endswith(IMAGE_EXTENSION):
        return (f"файл с изображением графа должен иметь расширение "
                f"{IMAGE_EXTENSION}: '{output}' (--output)")
    directory = os.path.dirname(output)
    if directory and not os.path.isdir(directory):
        return f"папка '{directory}' для файла графа не существует (--output)"
    return None


def validate_max_depth(value: str) -> str | None:
    """Проверяет максимальную глубину анализа зависимостей."""
    try:
        depth = int(value)
    except ValueError:
        return (f"максимальная глубина должна быть целым числом, "
                f"получено '{value}' (--max-depth)")
    if depth < MIN_MAX_DEPTH:
        return (f"максимальная глубина должна быть не меньше "
                f"{MIN_MAX_DEPTH}, получено {depth} (--max-depth)")
    return None


def validate_args(args: argparse.Namespace) -> list[str]:
    """Проверяет все параметры и возвращает список ошибок."""
    errors = [
        validate_package(args.package),
        validate_repo(args.repo, args.test_mode),
        validate_output(args.output),
        validate_max_depth(args.max_depth),
    ]
    return [error for error in errors if error]


def fetch(url: str) -> bytes:
    """Загружает данные по URL-адресу."""
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == HTTP_NOT_FOUND:
            raise NotFoundError(f"ресурс не найден: {url}") from error
        raise NuGetError(
            f"сервер вернул ошибку {error.code} для {url}") from error
    except OSError as error:
        reason = getattr(error, "reason", error)
        raise NuGetError(
            f"не удалось подключиться к {url}: {reason}") from error


def fetch_json(url: str) -> dict:
    """Загружает JSON-документ по URL-адресу."""
    try:
        data = json.loads(fetch(url))
    except ValueError as error:
        raise NuGetError(f"ответ {url} не является JSON") from error
    if not isinstance(data, dict):
        raise NuGetError(f"неожиданный формат ответа {url}")
    return data


def find_package_base(index: dict) -> str:
    """Находит в индексе сервиса NuGet адрес хранилища пакетов."""
    for resource in index.get("resources", []):
        if resource.get("@type") == PACKAGE_BASE_TYPE:
            return resource["@id"].rstrip("/") + "/"
    raise NuGetError("URL-адрес не является индексом сервиса NuGet V3: "
                     f"нет ресурса {PACKAGE_BASE_TYPE}")


def get_versions(base: str, package: str) -> list[str]:
    """Возвращает список версий пакета."""
    try:
        data = fetch_json(f"{base}{package.lower()}/index.json")
    except NotFoundError as error:
        raise NuGetError(
            f"пакет '{package}' не найден в репозитории") from error
    return data.get("versions", [])


def select_version(versions: list[str]) -> str:
    """Выбирает последнюю стабильную версию (или последнюю, если их нет)."""
    stable = [version for version in versions if "-" not in version]
    candidates = stable or versions
    if not candidates:
        raise NuGetError("у пакета нет опубликованных версий")
    return candidates[-1]


def parse_dependencies(nuspec: bytes) -> list[tuple[str, str]]:
    """Извлекает прямые зависимости из файла описания пакета .nuspec."""
    try:
        root = ElementTree.fromstring(nuspec)
    except ElementTree.ParseError as error:
        raise NuGetError("некорректный файл описания пакета") from error
    dependencies: dict[str, tuple[str, str]] = {}
    for element in root.iter():
        name = element.get("id")
        if element.tag.rsplit("}", 1)[-1] == "dependency" and name:
            dependencies.setdefault(name.lower(),
                                    (name, element.get("version", "")))
    return [dependencies[key] for key in sorted(dependencies)]


def get_direct_dependencies(
        repo_url: str, package: str) -> tuple[str, list[tuple[str, str]]]:
    """Возвращает версию пакета и его прямые зависимости."""
    try:
        index = fetch_json(repo_url)
    except NotFoundError as error:
        raise NuGetError(
            f"индекс сервиса NuGet не найден по адресу {repo_url}") from error
    base = find_package_base(index)
    version = select_version(get_versions(base, package))
    package_id = package.lower()
    nuspec = fetch(f"{base}{package_id}/{version.lower()}/"
                   f"{package_id}.nuspec")
    return version, parse_dependencies(nuspec)


def print_dependencies(package: str, version: str,
                       dependencies: list[tuple[str, str]]) -> None:
    """Выводит прямые зависимости пакета."""
    print(f"Пакет: {package} {version}")
    if not dependencies:
        print("Прямые зависимости: нет")
        return
    print(f"Прямые зависимости ({len(dependencies)}):")
    for name, version_range in dependencies:
        print(f"  {name} {version_range}".rstrip())


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Возвращает код завершения программы."""
    args = parse_args(argv)
    errors = validate_args(args)
    if args.test_mode:
        errors.append("режим тестового репозитория пока не поддерживается: "
                      "укажите URL-адрес репозитория (--test-mode)")
    if errors:
        for error in errors:
            print(f"Ошибка: {error}")
        return 1
    try:
        version, dependencies = get_direct_dependencies(args.repo,
                                                        args.package)
    except NuGetError as error:
        print(f"Ошибка: {error}")
        return 1
    print_dependencies(args.package, version, dependencies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
