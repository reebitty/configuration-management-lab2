import io
import os
import unittest
from contextlib import redirect_stdout

from src.main import (
    main,
    parse_args,
    validate_max_depth,
    validate_output,
    validate_package,
    validate_repo,
)

TEST_REPO = os.path.join(os.path.dirname(__file__), "..", "repos",
                         "test_repo.txt")
URL = "https://api.nuget.org/v3/index.json"


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


class TestMain(unittest.TestCase):
    """Тестирование запуска приложения."""

    def test_prints_config(self) -> None:
        """Тест вывода всех параметров в формате ключ-значение."""
        code, output = run_main(["-p", "A", "-r", TEST_REPO, "-t", "-a"])
        self.assertEqual(code, 0)
        for line in ("package: A", f"repo: {TEST_REPO}", "test_mode: True",
                     "output: graph.svg", "ascii_tree: True",
                     "max_depth: 3"):
            self.assertIn(line, output)

    def test_reports_all_errors(self) -> None:
        """Тест вывода всех ошибок и кода завершения 1."""
        code, output = run_main(["-p", "bad name!", "-r", "nuget",
                                 "-o", "graph.png", "-d", "0"])
        self.assertEqual(code, 1)
        self.assertEqual(output.count("Ошибка:"), 4)


if __name__ == "__main__":
    unittest.main()
