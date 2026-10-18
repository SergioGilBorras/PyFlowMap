"""Tests for the benchmark's own structural oracle, without PyFlowMap installed."""
import json
import unittest

from benchmark.evaluation import oracles_current, oracles_phase5_2
from benchmark.runners.run import CASES, check_sources, inspect_graph


class GraphOracleTests(unittest.TestCase):
    def test_default_runner_uses_declared_canonical_oracle(self):
        from benchmark.runners import run as runner
        self.assertEqual(oracles_current.VERSION, "phase5.2")
        self.assertIs(runner.evaluate_semantics, oracles_current.evaluate_semantics)
        self.assertIs(oracles_current.evaluate_semantics, oracles_phase5_2.evaluate_semantics)

    def setUp(self):
        self.graph = {
            'entry': 'demo:run',
            'nodes': [
                {'id': 'n1', 'kind': 'initial', 'locations': [], 'label_metadata': {}},
                {'id': 'n2', 'kind': 'decision', 'locations': ['demo.py:3'], 'label_metadata': {}},
                {'id': 'n3', 'kind': 'activity', 'locations': ['demo.py:5'],
                 'label_metadata': {'significant_call': True, 'call_expression': 'work'}},
                {'id': 'n4', 'kind': 'final', 'locations': [], 'label_metadata': {}},
            ],
            'edges': [
                {'source': 'n1', 'target': 'n2', 'label': ''},
                {'source': 'n2', 'target': 'n3', 'label': 'Sí'},
                {'source': 'n2', 'target': 'n4', 'label': 'No'},
                {'source': 'n3', 'target': 'n4', 'label': ''},
            ],
            'warnings': [],
        }

    def test_connected_graph_and_marked_call(self):
        marker = [{'file': 'demo.py', 'line': 5, 'source': 'work()'}]
        report = inspect_graph(self.graph, marker, 1)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['critical_direct'], 1)
        self.assertEqual(report['critical_missing'], 0)

    def test_detect_invalid_edge(self):
        self.graph['edges'].append({'source': 'n3', 'target': 'unknown', 'label': ''})
        self.assertTrue(inspect_graph(self.graph, [], 1)['errors'])

    def test_detect_unreachable_node(self):
        self.graph['nodes'].append({'id': 'n5', 'kind': 'activity', 'locations': [], 'label_metadata': {}})
        self.assertTrue(any('unreachable' in x for x in inspect_graph(self.graph, [], 1)['errors']))

    def test_missing_call_is_visible_in_report(self):
        marker = [{'file': 'demo.py', 'line': 99, 'source': 'missing()'}]
        report = inspect_graph(self.graph, marker, 1)
        self.assertEqual(report['critical_missing'], 1)
        self.assertTrue(report['warnings'])

    def test_nested_call_metadata_uses_its_own_source_location(self):
        self.graph['nodes'][2]['locations'] = ['demo.py:18']
        self.graph['nodes'][2]['label_metadata'] = {
            'subprocess_calls': [{'expression': 'notify', 'location': 'demo.py:14'}]
        }
        marker = [{'file': 'demo.py', 'line': 14, 'source': 'notify(task)'}]
        report = inspect_graph(self.graph, marker, 0)
        self.assertEqual(report['critical_direct'], 0)
        self.assertEqual(report['critical_metadata'], 1)
        self.assertEqual(report['critical_missing'], 0)

    def test_all_15_sources_are_parseable(self):
        cases = json.loads(CASES.read_text(encoding='utf-8'))['cases']
        self.assertEqual(len(cases), 15)
        self.assertTrue(all(check_sources(case)[0].exists() for case in cases))


if __name__ == '__main__':
    unittest.main()
