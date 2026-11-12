"""Solver-free regression tests for direct signed PE22 and ODB inventory."""
import csv
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / '00_Main_Scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def instance(name='I-PART-1', count=3):
    return types.SimpleNamespace(name=name, elements=[types.SimpleNamespace(label=i + 1, type='CPS3') for i in range(count)],
                                 nodes=[types.SimpleNamespace(coordinates=(0., 0., 0.)), types.SimpleNamespace(coordinates=(1., 2., 0.))])


def field(inst, numbers, labels=('PE11', 'PE22', 'PE33', 'PE12')):
    values = [types.SimpleNamespace(data=value, instance=inst, elementLabel=i + 1,
                                   integrationPoint=1, position='INTEGRATION_POINT') for i, value in enumerate(numbers)]
    scalar = types.SimpleNamespace(values=values)
    subset = types.SimpleNamespace(getScalarField=Mock(return_value=scalar))
    return types.SimpleNamespace(componentLabels=labels, getSubset=Mock(return_value=subset)), subset


def odb_fixture(numbers=(-0.3, 0., 0.6)):
    inst = instance(count=len(numbers))
    pe, subset = field(inst, numbers)
    frame = types.SimpleNamespace(frameValue=0.95, incrementNumber=190, fieldOutputs={'PE': pe})
    odb = types.SimpleNamespace(rootAssembly=types.SimpleNamespace(instances={'I-PART-1': inst}),
                                steps={'Loading': types.SimpleNamespace(frames=[frame])}, close=Mock())
    return odb, pe, subset


class DirectPe22Tests(unittest.TestCase):
    def setUp(self):
        self.export = load('abaqus_roi_report_export')
        self.constants = types.SimpleNamespace(INTEGRATION_POINT='INTEGRATION_POINT',
                                               COMMA_SEPARATED_VALUES='CSV', COMPONENT='COMPONENT', OFF=False, SPECIFY='SPECIFY')
        self.modules = patch.dict(sys.modules, {'abaqusConstants': self.constants})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_report_requests_signed_pe22_and_s22_at_integration_points(self):
        viewport = Mock()
        session = types.SimpleNamespace(viewports={'Viewport: 1': viewport}, fieldReportOptions=Mock(),
                                        DisplayGroup=Mock(), writeFieldReport=Mock())
        odb = types.SimpleNamespace(rootAssembly=types.SimpleNamespace(elementSets={'roi_left_01': object()}))
        roi = self.export.ROIRegion('roi_left_01', 'left', (0., 0.), 0.1)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {
                'visualization': types.SimpleNamespace(), 'abaqus': types.SimpleNamespace(session=session),
                'displayGroupOdbToolset': types.SimpleNamespace(LeafFromElementSets=Mock())}):
            self.export.export_roi_field_reports(odb, [roi], [7], tmp)
        request = session.writeFieldReport.call_args.kwargs
        self.assertEqual(request['variable'], (('S', 'INTEGRATION_POINT', (('COMPONENT', 'S22'),)),
                                               ('PE', 'INTEGRATION_POINT', (('COMPONENT', 'PE22'),))))
        self.assertEqual(request['frame'], 7)
        self.assertEqual(Path(request['fileName']).name, 'roi_left_01_frame7.csv')

    def test_domain_counts_do_not_call_abaqus_shadowed_sum(self):
        odb, _, _ = odb_fixture()
        # Abaqus/CAE can replace bare sum with a kernel numeric function that
        # rejects generators. Sign counts must not depend on that global name.
        with tempfile.TemporaryDirectory() as tmp, patch.object(
                self.export, 'sum', side_effect=TypeError('Abaqus sum rejects generator'), create=True):
            path = self.export.export_domain_pe22_summary(odb, [0], tmp)
            with open(path, newline='') as handle:
                row = next(csv.DictReader(handle))
        self.assertEqual([int(row[k]) for k in ('negative_count', 'zero_count', 'positive_count')], [1, 1, 1])
        self.assertAlmostEqual(float(row['average_plastic_strain']), 0.1)

    def test_global_signed_mean_counts_and_actual_frame_time(self):
        odb, pe, subset = odb_fixture()
        # Assembly reference-node instances must not contribute to the mean.
        odb.rootAssembly.instances['REFERENCE-POINT'] = instance('REFERENCE-POINT', count=0)
        with tempfile.TemporaryDirectory() as tmp:
            path = self.export.export_domain_pe22_summary(odb, [0], tmp)
            self.assertEqual(Path(path).name, 'domain_pe22_summary.csv')
            with open(path, newline='') as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertAlmostEqual(float(row['average_plastic_strain']), 0.1)
        self.assertEqual(float(row['min_pe22']), -0.3)
        self.assertEqual(float(row['max_pe22']), 0.6)
        self.assertEqual([int(row[k]) for k in ('negative_count', 'zero_count', 'positive_count', 'point_count')], [1, 1, 1, 3])
        self.assertEqual(int(row['frame_number']), 0)
        self.assertEqual(float(row['step_time']), 0.95)
        pe.getSubset.assert_called_once_with(region=odb.rootAssembly.instances['I-PART-1'])
        subset.getScalarField.assert_called_once_with(componentLabel='PE22')

    def test_no_mean_of_instance_means_or_unrelated_model_instances(self):
        odb, _, _ = odb_fixture()
        odb.rootAssembly.instances['OTHER'] = instance('OTHER', count=1)
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, 'single|one'):
            self.export.export_domain_pe22_summary(odb, [0], tmp)
        self.assertNotEqual(odb.rootAssembly.instances['OTHER'].name, 'I-PART-1')

    def test_missing_pe_or_component_never_uses_elastic_subtraction(self):
        for fields in ({'E': object(), 'S': object()}, {'PE': types.SimpleNamespace(componentLabels=('PE11', 'PE12'))}):
            odb, _, _ = odb_fixture()
            odb.steps['Loading'].frames[0].fieldOutputs = fields
            with self.subTest(fields=list(fields)), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(ValueError, 'PE|PE22'):
                    self.export.export_domain_pe22_summary(odb, [0], tmp)
                self.assertFalse((Path(tmp) / 'domain_pe22_summary.csv').exists())

    def test_nonfinite_missing_foreign_or_duplicate_points_rejected(self):
        for defect in ('nan', 'empty', 'foreign', 'duplicate', 'nodal'):
            odb, _, subset = odb_fixture()
            values = subset.getScalarField.return_value.values
            if defect == 'nan': values[0].data = float('nan')
            if defect == 'empty': del values[:]
            if defect == 'foreign': values[0].instance = instance('OTHER')
            if defect == 'duplicate': values[1].elementLabel = values[0].elementLabel
            if defect == 'nodal': values[0].position = 'NODAL'
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    self.export.export_domain_pe22_summary(odb, [0], tmp)

    def test_main_calls_domain_summary_after_roi_reports_with_same_frames_and_instance(self):
        odb, _, _ = odb_fixture()
        session = types.SimpleNamespace(openOdb=Mock(return_value=odb))
        calls = Mock()
        config = {'frames': [0], 'domain_size': [1, 1], 'instance_name': 'I-PART-1', 'output_folder': 'reports'}
        with patch.dict(sys.modules, {'abaqus': types.SimpleNamespace(session=session)}), \
                patch.object(self.export, 'load_config', return_value=config), \
                patch.object(self.export, 'find_odb_file', return_value='fixture.odb'), \
                patch.object(self.export, 'restore_clean_odb_if_available'), \
                patch.object(self.export, 'save_clean_odb_backup_if_missing'), \
                patch.object(self.export, 'require_no_existing_roi_sets'), \
                patch.object(self.export, 'create_roi_sets', return_value={}), \
                patch.object(self.export, 'export_roi_field_reports', calls.roi), \
                patch.object(self.export, 'export_domain_pe22_summary', calls.domain):
            self.export.main()
        self.assertEqual([call[0] for call in calls.mock_calls], ['roi', 'domain'])
        calls.domain.assert_called_once_with(odb, [0], 'reports', instance_name='I-PART-1')

    def test_main_defaults_to_separate_pe22_output_folder(self):
        odb, _, _ = odb_fixture()
        config = {'frames': [0], 'domain_size': [1, 1], 'instance_name': 'I-PART-1'}
        session = types.SimpleNamespace(openOdb=Mock(return_value=odb))
        with patch.dict(sys.modules, {'abaqus': types.SimpleNamespace(session=session)}), \
                patch.object(self.export, 'load_config', return_value=config), \
                patch.object(self.export, 'find_odb_file', return_value='fixture.odb'), \
                patch.object(self.export, 'restore_clean_odb_if_available'), \
                patch.object(self.export, 'save_clean_odb_backup_if_missing'), \
                patch.object(self.export, 'require_no_existing_roi_sets'), \
                patch.object(self.export, 'create_roi_sets', return_value={}), \
                patch.object(self.export, 'export_roi_field_reports') as roi, \
                patch.object(self.export, 'export_domain_pe22_summary') as domain:
            self.export.main()
        self.assertEqual(roi.call_args.kwargs['output_folder'], '../roi_reports_pe22')
        self.assertEqual(domain.call_args.args[2], '../roi_reports_pe22')

    def test_selected_frames_keep_first_step_index_not_increment(self):
        odb, _, _ = odb_fixture()
        frame = odb.steps['Loading'].frames[0]
        odb.steps['Loading'].frames = [frame, types.SimpleNamespace(frameValue=1.23, incrementNumber=246, fieldOutputs=frame.fieldOutputs)]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.export.export_domain_pe22_summary(odb, [1, 0], tmp)
            with open(path, newline='') as handle: rows = list(csv.DictReader(handle))
        self.assertEqual([int(row['frame_number']) for row in rows], [1, 0])
        self.assertEqual([float(row['step_time']) for row in rows], [1.23, 0.95])


class InventoryTests(unittest.TestCase):
    def test_readonly_inventory_format_and_original_odb_path(self):
        module = load('abaqus_odb_frame_inventory')
        odb, _, _ = odb_fixture()
        opener = Mock(return_value=odb)
        with tempfile.TemporaryDirectory() as tmp:
            source = str(Path(tmp) / 'original.odb')
            output = str(Path(tmp) / 'odb_inventory.json')
            with patch.dict(sys.modules, {'odbAccess': types.SimpleNamespace(openOdb=opener)}):
                module.export_odb_inventory(source, output)
            record = json.loads(Path(output).read_text())
        opener.assert_called_once_with(path=source, readOnly=True)
        odb.close.assert_called_once_with()
        self.assertEqual(record['odb'], source)
        self.assertEqual(record['instances'], [{'name': 'I-PART-1', 'nodes': 2, 'elements': 3,
                                              'element_types': ['CPS3'], 'bounds': [0., 1., 0., 2.]}])
        frame = record['steps'][0]['frames'][0]
        self.assertEqual(record['steps'][0]['name'], 'Loading')
        self.assertEqual({k: frame[k] for k in ('index', 'time', 'increment', 'fields')},
                         {'index': 0, 'time': 0.95, 'increment': 190, 'fields': ['PE']})
        self.assertIn('PE22', frame['component_labels']['PE'])

    def test_main_env_stem_or_filename_and_single_odb_fallback(self):
        module = load('abaqus_odb_frame_inventory')
        for env in ('original', 'original.odb', None):
            with self.subTest(env=env), tempfile.TemporaryDirectory() as tmp:
                old = os.getcwd()
                try:
                    os.chdir(tmp)
                    Path('original.odb').write_bytes(b'fixture only')
                    with patch.dict(os.environ, {}, clear=True), patch.object(module, 'export_odb_inventory') as export:
                        if env is not None: os.environ['ODB_FILE'] = env
                        module.main()
                        export.assert_called_once_with(os.path.abspath('original.odb'), os.path.abspath('../odb_inventory.json'))
                finally:
                    os.chdir(old)

    def test_main_honors_explicit_inventory_output_without_touching_old_inventory(self):
        module = load('abaqus_odb_frame_inventory')
        with patch.dict(os.environ, {'ODB_FILE': 'original', 'ODB_INVENTORY_OUTPUT': '../odb_inventory_pe22.json'}), \
                patch.object(module, 'export_odb_inventory') as export:
            module.main()
        export.assert_called_once_with(os.path.abspath('original.odb'), os.path.abspath('../odb_inventory_pe22.json'))

    def test_fallback_refuses_ambiguous_odb_files(self):
        module = load('abaqus_odb_frame_inventory')
        with patch.dict(os.environ, {}, clear=True), patch.object(module.os, 'listdir', return_value=['a.odb', 'b.odb']):
            with self.assertRaises(ValueError): module.main()


if __name__ == '__main__':
    unittest.main()
