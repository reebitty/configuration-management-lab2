import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable
from dataclasses import dataclass, field
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
REQUEST_ATTEMPTS = 3
HTTP_NOT_FOUND = 404
PACKAGE_BASE_TYPE = "PackageBaseAddress/3.0.0"
TEST_PACKAGE_PATTERN = re.compile(r"^[A-Z]+$")


class NuGetError(Exception):
    """Ошибка получения данных из репозитория NuGet."""


class NotFoundError(NuGetError):
    """Запрошенный ресурс отсутствует в репозитории."""


class RepoError(Exception):
    """Ошибка загрузки тестового репозитория."""


@dataclass
class DependencyGraph:
    """Граф зависимостей: пакет -> список зависимостей.

    Значение None означает, что зависимости пакета не анализировались,
    так как достигнута максимальная глубина.
    """

    max_depth: int
    nodes: dict[str, list[str] | None] = field(default_factory=dict)
    depths: dict[str, int] = field(default_factory=dict)
    cycles: list[list[str]] = field(default_factory=list)
    cycle_keys: set[tuple[str, ...]] = field(default_factory=set)


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
    parser.add_argument("-R", "--reverse", action="store_true",
                        help="вывод обратных зависимостей: пакетов, "
                             "которые зависят от заданного пакета "
                             "(только с --test-mode)")
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


def validate_reverse(reverse: bool, test_mode: bool) -> str | None:
    """Проверяет, что обратные зависимости ищутся в тестовом репозитории."""
    if reverse and not test_mode:
        return ("режим обратных зависимостей поддерживается только для "
                "тестового репозитория: укажите --test-mode (--reverse)")
    return None


def validate_args(args: argparse.Namespace) -> list[str]:
    """Проверяет все параметры и возвращает список ошибок."""
    errors = [
        validate_package(args.package),
        validate_repo(args.repo, args.test_mode),
        validate_output(args.output),
        validate_max_depth(args.max_depth),
        validate_reverse(args.reverse, args.test_mode),
    ]
    return [error for error in errors if error]


def fetch_once(url: str) -> bytes:
    """Выполняет один запрос по URL-адресу."""
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == HTTP_NOT_FOUND:
            raise NotFoundError(f"ресурс не найден: {url}") from error
        raise NuGetError(
            f"сервер вернул ошибку {error.code} для {url}") from error


def fetch(url: str) -> bytes:
    """Загружает данные по URL-адресу, повторяя запрос при сбое сети."""
    for attempt in range(1, REQUEST_ATTEMPTS + 1):
        try:
            return fetch_once(url)
        except OSError as error:
            if attempt == REQUEST_ATTEMPTS:
                reason = getattr(error, "reason", error)
                raise NuGetError(
                    f"не удалось подключиться к {url}: {reason}") from error
    raise NuGetError(f"не удалось подключиться к {url}")


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


def make_nuget_resolver(repo_url: str) -> Callable[[str], list[str]]:
    """Создает функцию получения прямых зависимостей пакета из NuGet."""
    try:
        index = fetch_json(repo_url)
    except NotFoundError as error:
        raise NuGetError(
            f"индекс сервиса NuGet не найден по адресу {repo_url}") from error
    base = find_package_base(index)
    cache: dict[str, list[str]] = {}

    def get_dependencies(package: str) -> list[str]:
        """Возвращает имена прямых зависимостей последней версии пакета."""
        package_id = package.lower()
        if package_id not in cache:
            version = select_version(get_versions(base, package))
            nuspec = fetch(f"{base}{package_id}/{version.lower()}/"
                           f"{package_id}.nuspec")
            cache[package_id] = [name for name, _ in
                                 parse_dependencies(nuspec)]
        return cache[package_id]

    return get_dependencies


def parse_test_line(line: str, number: int) -> tuple[str, list[str]]:
    """Разбирает строку тестового репозитория вида 'A: B C'."""
    if ":" not in line:
        raise RepoError(f"строка {number}: ожидается формат "
                        "'ПАКЕТ: ЗАВИСИМОСТИ'")
    name, _, rest = line.partition(":")
    names = [name.strip()] + rest.split()
    for package in names:
        if not TEST_PACKAGE_PATTERN.match(package):
            raise RepoError(f"строка {number}: недопустимое имя пакета "
                            f"'{package}' (только большие латинские буквы)")
    return names[0], names[1:]


def load_test_repo(path: str) -> dict[str, list[str]]:
    """Загружает граф тестового репозитория из файла."""
    try:
        with open(path, encoding="utf-8-sig") as file:
            lines = file.readlines()
    except OSError as error:
        raise RepoError(f"не удалось открыть файл тестового репозитория "
                        f"'{path}': {error.strerror}") from error
    repo: dict[str, list[str]] = {}
    for number, line in enumerate(lines, start=1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, dependencies = parse_test_line(line, number)
        if name in repo:
            raise RepoError(f"строка {number}: пакет '{name}' описан "
                            "повторно")
        repo[name] = dependencies
    return repo


def reverse_repo(repo: dict[str, list[str]]) -> dict[str, list[str]]:
    """Переворачивает граф: пакет -> пакеты, которые от него зависят."""
    dependents: dict[str, list[str]] = {}
    for name, dependencies in repo.items():
        for dependency in dependencies:
            dependents.setdefault(dependency, []).append(name)
    return {name: sorted(names) for name, names in dependents.items()}


def make_test_resolver(path: str, package: str,
                       reverse: bool = False) -> Callable[[str], list[str]]:
    """Создает функцию получения зависимостей из тестового репозитория.

    При reverse=True функция возвращает обратные зависимости: пакеты,
    которые напрямую зависят от заданного пакета.
    """
    repo = load_test_repo(path)
    known = set(repo)
    for dependencies in repo.values():
        known.update(dependencies)
    if package not in known:
        raise RepoError(f"пакет '{package}' не найден в тестовом "
                        "репозитории")
    if reverse:
        repo = reverse_repo(repo)
    return lambda name: repo.get(name, [])


def add_cycle(graph: DependencyGraph, cycle: list[str]) -> None:
    """Добавляет найденный цикл в граф, если он еще не был найден."""
    nodes = cycle[:-1]
    start = nodes.index(min(nodes))
    key = tuple(nodes[start:] + nodes[:start])
    if key not in graph.cycle_keys:
        graph.cycle_keys.add(key)
        graph.cycles.append(list(key) + [key[0]])


def visit(graph: DependencyGraph, package: str, depth: int,
          path: list[str],
          get_dependencies: Callable[[str], list[str]]) -> None:
    """Рекурсивно обходит зависимости пакета в глубину (DFS)."""
    if package in path:
        add_cycle(graph, path[path.index(package):] + [package])
        return
    if package in graph.depths and graph.depths[package] <= depth:
        return
    graph.depths[package] = depth
    if depth >= graph.max_depth:
        graph.nodes.setdefault(package, None)
        return
    dependencies = get_dependencies(package)
    graph.nodes[package] = dependencies
    path.append(package)
    for dependency in dependencies:
        visit(graph, dependency, depth + 1, path, get_dependencies)
    path.pop()


def collect_cycles(graph: DependencyGraph, package: str, path: list[str],
                   done: set[str]) -> None:
    """Рекурсивно ищет циклы в построенном графе обходом в глубину."""
    if package in path:
        add_cycle(graph, path[path.index(package):] + [package])
        return
    if package in done:
        return
    path.append(package)
    for dependency in graph.nodes.get(package) or []:
        collect_cycles(graph, dependency, path, done)
    path.pop()
    done.add(package)


def build_graph(package: str, max_depth: int,
                get_dependencies: Callable[[str], list[str]]
                ) -> DependencyGraph:
    """Строит граф зависимостей пакета с учетом транзитивности.

    После обхода граф проверяется еще раз, чтобы найти циклы, которые
    видны в итоговом графе, но не лежали на одном пути при обходе
    (например, из-за ограничения глубины).
    """
    graph = DependencyGraph(max_depth)
    visit(graph, package, 0, [], get_dependencies)
    done: set[str] = set()
    for name in list(graph.nodes):
        collect_cycles(graph, name, [], done)
    return graph


def print_graph(package: str, graph: DependencyGraph,
                reverse: bool = False) -> None:
    """Выводит граф зависимостей (или обратных зависимостей) и циклы.

    В режиме обратных зависимостей запись 'X <- Y, Z' означает,
    что пакеты Y и Z зависят от пакета X.
    """
    title = "Обратные зависимости" if reverse else "Граф зависимостей"
    arrow = " <- " if reverse else " -> "
    print(f"{title} пакета {package} "
          f"(максимальная глубина: {graph.max_depth})")
    for name, dependencies in graph.nodes.items():
        if dependencies is None:
            print(f"  {name}{arrow}не анализировался "
                  "(достигнута максимальная глубина)")
        else:
            print(f"  {name}{arrow}{', '.join(dependencies) or 'нет'}")
    if reverse:
        print(f"Пакетов, зависящих от {package}: {len(graph.nodes) - 1}")
    else:
        print(f"Пакетов в графе: {len(graph.nodes)}")
    if not graph.cycles:
        print("Циклические зависимости: нет")
        return
    print(f"Циклические зависимости ({len(graph.cycles)}):")
    for cycle in graph.cycles:
        print("  " + arrow.join(cycle))


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Возвращает код завершения программы."""
    args = parse_args(argv)
    errors = validate_args(args)
    if errors:
        for error in errors:
            print(f"Ошибка: {error}")
        return 1
    try:
        if args.test_mode:
            resolver = make_test_resolver(args.repo, args.package,
                                          args.reverse)
        else:
            resolver = make_nuget_resolver(args.repo)
        graph = build_graph(args.package, int(args.max_depth), resolver)
    except (NuGetError, RepoError) as error:
        print(f"Ошибка: {error}")
        return 1
    print_graph(args.package, graph, args.reverse)
    return 0


if __name__ == "__main__":
    sys.exit(main())
