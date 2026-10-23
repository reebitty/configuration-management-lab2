import argparse
import os
import re
import sys
from urllib.parse import urlparse

DEFAULT_OUTPUT = "graph.svg"
DEFAULT_MAX_DEPTH = 3
MIN_MAX_DEPTH = 1
MAX_PACKAGE_LENGTH = 100
PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
URL_SCHEMES = ("http", "https")
IMAGE_EXTENSION = ".svg"
FORBIDDEN_FILE_CHARS = '<>:"|?*'


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


def make_config(args: argparse.Namespace) -> dict[str, object]:
    """Собирает проверенные параметры в словарь ключ-значение."""
    return {
        "package": args.package,
        "repo": args.repo,
        "test_mode": args.test_mode,
        "output": args.output,
        "ascii_tree": args.ascii_tree,
        "max_depth": int(args.max_depth),
    }


def print_config(config: dict[str, object]) -> None:
    """Выводит все параметры в формате ключ-значение."""
    print("Параметры запуска:")
    for key, value in config.items():
        print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Возвращает код завершения программы."""
    args = parse_args(argv)
    errors = validate_args(args)
    if errors:
        for error in errors:
            print(f"Ошибка: {error}")
        return 1
    print_config(make_config(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
