import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src.main import (
    NotFoundError,
    NuGetError,
    find_package_base,
    main,
    parse_args,
    parse_dependencies,
    select_version,
    validate_max_depth,
    validate_output,
    validate_package,
    validate_repo,
)

TEST_REPO = os.path.join(os.path.dirname(__file__), "..", "repos",
                         "test_repo.txt")
URL = "https://api.nuget.org/v3/index.json"
BASE = "https://example.org/flat/"
INDEX = {"resources": [
    {"@id": "https://example.org/search", "@type": "SearchQueryService"},
    {"@id": "https://example.org/flat", "@type": "PackageBaseAddress/3.0.0"},
]}
NUSPEC = b"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">
  <metadata>
    <id>Demo</id>
    <dependencies>
      <group targetFramework="net6.0">
        <dependency id="lib.b" version="[2.0, 3.0)" />
        <dependency id="Lib.A" version="1.0.0" />
      </group>
      <group targetFramework="netstandard2.0">
        <dependency id="Lib.A" version="1.0.0" />
      </group>
    </dependencies>
  </metadata>
</package>"""
FAKE_RESPONSES = {
    URL: json.dumps(INDEX).encode(),
    BASE + "demo/index.json": b'{"versions": ["1.0.0", "2.0.0"]}',
    BASE + "demo/2.0.0/demo.nuspec": NUSPEC,
}


def fake_fetch(url: str) -> bytes:
    """Подменяет загрузку по сети заранее заданными ответами."""
    if url not in FAKE_RESPONSES:
        raise NotFoundError(f"ресурс не найден: {url}")
    return FAKE_RESPONSES[url]


def run_main(argv: list[str]) -> tuple[int, str]:
    """Запускает приложение и возвращает код завершения и вывод."""
    output = io.StringIO()
    with redirect_stdout(output):
        code = main(argv)
    return code, output.getvalue()


class TestParseArgs(unittest.TestCase):
    """Тестирование разбора параметров командной строки."""

    def test_all_options(self) -> None:
        """Тест разбора всех параметров в полной форме."""
        args = parse_args(["--package", "A", "--repo", "r.txt",
                           "--test-mode", "--output", "g.svg",
                           "--ascii-tree", "--max-depth", "5"])
        self.assertEqual(args.package, "A")
        self.assertEqual(args.repo, "r.txt")
        self.assertTrue(args.test_mode)
        self.assertEqual(args.output, "g.svg")
        self.assertTrue(args.ascii_tree)
        self.assertEqual(args.max_depth, "5")

    def test_defaults(self) -> None:
        """Тест значений по умолчанию."""
        args = parse_args([])
        self.assertIsNone(args.package)
        self.assertFalse(args.test_mode)
        self.assertEqual(args.output, "graph.svg")
        self.assertFalse(args.ascii_tree)
        self.assertEqual(args.max_depth, "3")


class TestValidation(unittest.TestCase):
    """Тестирование проверки каждого параметра."""

    def test_package(self) -> None:
        """Тест проверки имени пакета."""
        self.assertIsNone(validate_package("Newtonsoft.Json"))
        self.assertIsNotNone(validate_package(None))
        self.assertIsNotNone(validate_package("bad name!"))
        self.assertIsNotNone(validate_package("A" * 101))

    def test_repo_url(self) -> None:
        """Тест проверки URL-адреса репозитория."""
        self.assertIsNone(validate_repo(URL, False))
        self.assertIsNotNone(validate_repo(None, False))
        self.assertIsNotNone(validate_repo("ftp://nuget.org", False))
        self.assertIsNotNone(validate_repo("nuget", False))

    def test_repo_test_mode(self) -> None:
        """Тест проверки пути к тестовому репозиторию."""
        self.assertIsNone(validate_repo(TEST_REPO, True))
        self.assertIsNotNone(validate_repo("missing.txt", True))
        self.assertIsNotNone(validate_repo(TEST_REPO, False))

    def test_output(self) -> None:
        """Тест проверки имени файла с изображением графа."""
        self.assertIsNone(validate_output("graph.svg"))
        self.assertIsNotNone(validate_output("graph.png"))
        self.assertIsNotNone(validate_output("gr*ph.svg"))
        self.assertIsNotNone(validate_output("missing_dir/graph.svg"))
        self.assertIsNotNone(validate_output(""))

    def test_max_depth(self) -> None:
        """Тест проверки максимальной глубины анализа."""
        self.assertIsNone(validate_max_depth("1"))
        self.assertIsNotNone(validate_max_depth("abc"))
        self.assertIsNotNone(validate_max_depth("0"))
        self.assertIsNotNone(validate_max_depth("-5"))


class TestNuGet(unittest.TestCase):
    """Тестирование получения прямых зависимостей из NuGet."""

    def test_find_package_base(self) -> None:
        """Тест поиска адреса хранилища пакетов в индексе сервиса."""
        self.assertEqual(find_package_base(INDEX), BASE)
        with self.assertRaises(NuGetError):
            find_package_base({"resources": []})

    def test_select_version(self) -> None:
        """Тест выбора последней стабильной версии."""
        self.assertEqual(select_version(["1.0.0", "2.0.0", "3.0.0-beta"]),
                         "2.0.0")
        self.assertEqual(select_version(["1.0.0-alpha"]), "1.0.0-alpha")
        with self.assertRaises(NuGetError):
            select_version([])

    def test_parse_dependencies(self) -> None:
        """Тест извлечения зависимостей из групп без повторов."""
        self.assertEqual(parse_dependencies(NUSPEC),
                         [("Lib.A", "1.0.0"), ("lib.b", "[2.0, 3.0)")])
        with self.assertRaises(NuGetError):
            parse_dependencies(b"not xml")

    def test_main_prints_dependencies(self) -> None:
        """Тест вывода прямых зависимостей пакета."""
        with patch("src.main.fetch", side_effect=fake_fetch):
            code, output = run_main(["-p", "Demo", "-r", URL])
        self.assertEqual(code, 0)
        self.assertEqual(output, "Пакет: Demo 2.0.0\n"
                                 "Прямые зависимости (2):\n"
                                 "  Lib.A 1.0.0\n"
                                 "  lib.b [2.0, 3.0)\n")

    def test_main_package_not_found(self) -> None:
        """Тест ошибки при отсутствии пакета в репозитории."""
        with patch("src.main.fetch", side_effect=fake_fetch):
            code, output = run_main(["-p", "Missing", "-r", URL])
        self.assertEqual(code, 1)
        self.assertIn("пакет 'Missing' не найден", output)

    def test_main_test_mode_not_supported(self) -> None:
        """Тест сообщения о неподдерживаемом режиме тестирования."""
        code, output = run_main(["-p", "A", "-r", TEST_REPO, "-t"])
        self.assertEqual(code, 1)
        self.assertIn("--test-mode", output)


class TestMain(unittest.TestCase):
    """Тестирование запуска приложения."""

    def test_reports_all_errors(self) -> None:
        """Тест вывода всех ошибок и кода завершения 1."""
        code, output = run_main(["-p", "bad name!", "-r", "nuget",
                                 "-o", "graph.png", "-d", "0"])
        self.assertEqual(code, 1)
        self.assertEqual(output.count("Ошибка:"), 4)


if __name__ == "__main__":
    unittest.main()
