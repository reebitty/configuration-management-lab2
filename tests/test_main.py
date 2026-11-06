import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src.main import (
    NotFoundError,
    NuGetError,
    RepoError,
    build_graph,
    fetch,
    find_package_base,
    load_test_repo,
    main,
    make_nuget_resolver,
    make_test_resolver,
    parse_args,
    parse_dependencies,
    parse_test_line,
    reverse_repo,
    validate_reverse,
    select_version,
    validate_max_depth,
    validate_output,
    validate_package,
    validate_repo,
)

REPOS = os.path.join(os.path.dirname(__file__), "..", "repos")
TEST_REPO = os.path.join(REPOS, "test_repo.txt")
CYCLE_REPO = os.path.join(REPOS, "cycle.txt")
CHAIN_REPO = os.path.join(REPOS, "chain.txt")
LIBRARY_REPO = os.path.join(REPOS, "library.txt")
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

    def test_fetch_retries_on_network_error(self) -> None:
        """Тест повтора запроса при сбое сети и без повтора при 404."""
        with patch("src.main.fetch_once",
                   side_effect=[OSError("eof"), OSError("eof"), b"ok"]):
            self.assertEqual(fetch(URL), b"ok")
        with patch("src.main.fetch_once", side_effect=OSError("eof")):
            with self.assertRaises(NuGetError):
                fetch(URL)
        with patch("src.main.fetch_once",
                   side_effect=NotFoundError("нет")) as fetch_once:
            with self.assertRaises(NotFoundError):
                fetch(URL)
            self.assertEqual(fetch_once.call_count, 1)

    def test_nuget_resolver(self) -> None:
        """Тест получения имен прямых зависимостей с кэшированием."""
        with patch("src.main.fetch", side_effect=fake_fetch) as fetch:
            resolver = make_nuget_resolver(URL)
            self.assertEqual(resolver("Demo"), ["Lib.A", "lib.b"])
            calls = fetch.call_count
            self.assertEqual(resolver("DEMO"), ["Lib.A", "lib.b"])
            self.assertEqual(fetch.call_count, calls)

    def test_main_nuget_graph(self) -> None:
        """Тест вывода графа пакета из репозитория NuGet."""
        with patch("src.main.fetch", side_effect=fake_fetch):
            code, output = run_main(["-p", "Demo", "-r", URL, "-d", "1"])
        self.assertEqual(code, 0)
        self.assertIn("Demo -> Lib.A, lib.b", output)
        self.assertIn("Lib.A -> не анализировался", output)

    def test_main_package_not_found(self) -> None:
        """Тест ошибки при отсутствии пакета в репозитории."""
        with patch("src.main.fetch", side_effect=fake_fetch):
            code, output = run_main(["-p", "Missing", "-r", URL])
        self.assertEqual(code, 1)
        self.assertIn("пакет 'Missing' не найден", output)


def graph_of(package: str, path: str, depth: int) -> dict:
    """Строит граф пакета из файла тестового репозитория."""
    graph = build_graph(package, depth, make_test_resolver(path, package))
    return {"nodes": graph.nodes, "cycles": graph.cycles}


class TestTestRepo(unittest.TestCase):
    """Тестирование загрузки тестового репозитория."""

    def test_parse_line(self) -> None:
        """Тест разбора строки описания пакета."""
        self.assertEqual(parse_test_line("A: B C", 1), ("A", ["B", "C"]))
        self.assertEqual(parse_test_line("D:", 1), ("D", []))
        for line in ("A B", "a: B", "A: B1"):
            with self.assertRaises(RepoError):
                parse_test_line(line, 1)

    def test_load(self) -> None:
        """Тест загрузки файла с комментариями."""
        self.assertEqual(load_test_repo(CHAIN_REPO)["E"], ["F"])
        with self.assertRaises(RepoError):
            load_test_repo("missing_repo.txt")

    def test_package_not_found(self) -> None:
        """Тест ошибки для пакета, которого нет в репозитории."""
        with self.assertRaises(RepoError):
            make_test_resolver(TEST_REPO, "Z")


class TestGraph(unittest.TestCase):
    """Тестирование построения графа алгоритмом DFS."""

    def test_shared_dependency(self) -> None:
        """Тест общей зависимости: пакет D анализируется один раз."""
        result = graph_of("A", TEST_REPO, 3)
        self.assertEqual(result["nodes"], {"A": ["B", "C"], "B": ["D"],
                                           "D": [], "C": ["D"]})
        self.assertEqual(result["cycles"], [])

    def test_cycles(self) -> None:
        """Тест обнаружения циклов, в том числе зависимости от себя."""
        result = graph_of("A", CYCLE_REPO, 5)
        self.assertEqual(result["cycles"], [["A", "B", "C", "A"],
                                            ["E", "E"]])
        self.assertEqual(len(result["nodes"]), 5)

    def test_cycle_found_once(self) -> None:
        """Тест: один и тот же цикл не дублируется."""
        result = graph_of("C", CYCLE_REPO, 10)
        self.assertEqual(result["cycles"].count(["A", "B", "C", "A"]), 1)

    def test_max_depth(self) -> None:
        """Тест ограничения глубины анализа."""
        result = graph_of("A", CHAIN_REPO, 2)
        self.assertEqual(result["nodes"], {"A": ["B"], "B": ["C"],
                                           "C": None})

    def test_shorter_path_expands_node(self) -> None:
        """Тест: пакет, найденный глубже, раскрывается по короткому пути."""
        repo = {"A": ["B", "D"], "B": ["C"], "C": ["D"], "D": ["E"]}
        graph = build_graph("A", 2, lambda name: repo.get(name, []))
        self.assertEqual(graph.nodes["D"], ["E"])
        self.assertIsNone(graph.nodes["E"])

    def test_cycle_after_shorter_path(self) -> None:
        """Тест: цикл находится, даже если он не лежал на одном пути."""
        repo = {"S": ["C", "D"], "C": ["B"], "B": ["A"], "D": ["A"],
                "A": ["C"]}
        graph = build_graph("S", 3, lambda name: repo.get(name, []))
        self.assertEqual(graph.nodes["A"], ["C"])
        self.assertEqual(graph.cycles, [["A", "C", "B", "A"]])

    def test_main_output(self) -> None:
        """Тест вывода графа и циклов на экран."""
        code, output = run_main(["-p", "B", "-r", CYCLE_REPO, "-t"])
        self.assertEqual(code, 0)
        self.assertIn("D -> не анализировался", output)
        self.assertIn("A -> B -> C -> A", output)
        self.assertIn("Пакетов в графе: 5", output)


def reverse_graph_of(package: str, path: str, depth: int) -> dict:
    """Строит граф обратных зависимостей пакета из тестового файла."""
    resolver = make_test_resolver(path, package, reverse=True)
    graph = build_graph(package, depth, resolver)
    return {"nodes": graph.nodes, "cycles": graph.cycles}


class TestReverse(unittest.TestCase):
    """Тестирование режима обратных зависимостей."""

    def test_reverse_repo(self) -> None:
        """Тест переворота графа: пакет -> кто от него зависит."""
        repo = {"A": ["B", "C"], "B": ["C"], "C": []}
        self.assertEqual(reverse_repo(repo), {"B": ["A"], "C": ["A", "B"]})

    def test_shared_dependency(self) -> None:
        """Тест: от D зависят B и C напрямую и A транзитивно."""
        result = reverse_graph_of("D", TEST_REPO, 3)
        self.assertEqual(result["nodes"], {"D": ["B", "C"], "B": ["A"],
                                           "A": [], "C": ["A"]})

    def test_direct_and_transitive(self) -> None:
        """Тест прямых и транзитивных обратных зависимостей."""
        result = reverse_graph_of("L", LIBRARY_REPO, 10)
        self.assertEqual(set(result["nodes"]),
                         {"L", "A", "B", "C", "D", "E", "F", "G"})
        self.assertEqual(result["nodes"]["L"], ["B", "D", "E"])

    def test_max_depth(self) -> None:
        """Тест ограничения глубины: только прямые обратные зависимости."""
        result = reverse_graph_of("L", LIBRARY_REPO, 1)
        self.assertEqual(result["nodes"], {"L": ["B", "D", "E"], "B": None,
                                           "D": None, "E": None})

    def test_no_dependents(self) -> None:
        """Тест пакета, от которого никто не зависит."""
        self.assertEqual(reverse_graph_of("F", LIBRARY_REPO, 3)["nodes"],
                         {"F": []})

    def test_cycles(self) -> None:
        """Тест циклов в графе обратных зависимостей."""
        result = reverse_graph_of("E", CYCLE_REPO, 3)
        self.assertIn(["E", "E"], result["cycles"])
        self.assertIn(["A", "C", "B", "A"], result["cycles"])

    def test_validate_reverse(self) -> None:
        """Тест: режим обратных зависимостей только для тестового режима."""
        self.assertIsNone(validate_reverse(True, True))
        self.assertIsNone(validate_reverse(False, False))
        self.assertIsNotNone(validate_reverse(True, False))

    def test_main_output(self) -> None:
        """Тест вывода обратных зависимостей на экран."""
        code, output = run_main(["-p", "D", "-r", TEST_REPO, "-t", "-R"])
        self.assertEqual(code, 0)
        self.assertIn("Обратные зависимости пакета D", output)
        self.assertIn("D <- B, C", output)
        self.assertIn("Пакетов, зависящих от D: 3", output)


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
