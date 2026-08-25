import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "00_Main_Scripts" / "roi_plotting.py"


def load_module():
    spec = importlib.util.spec_from_file_location("roi_plotting", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RoiPlottingTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_format_roi_label_puts_side_first_and_uses_all_caps_roi(self):
        self.assertEqual(self.module.format_roi_label("roi_left_01"), "Left ROI 01")
        self.assertEqual(self.module.format_roi_label("roi_right_09"), "Right ROI 09")

    def test_roi_ordering_supports_side_grouped_and_height_paired_views(self):
        roi_names = ["roi_right_02", "roi_left_01", "roi_right_01", "roi_left_02"]
        self.assertEqual(
            self.module.ordered_roi_names(roi_names, mode="grouped_by_side"),
            ["roi_left_01", "roi_left_02", "roi_right_01", "roi_right_02"],
        )
        self.assertEqual(
            self.module.ordered_roi_names(roi_names, mode="paired_by_height"),
            ["roi_left_01", "roi_right_01", "roi_left_02", "roi_right_02"],
        )

    def test_frame_context_uses_nearest_global_cycle_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "case.csv"
            csv_path.write_text(
                "ODB file name: case\n\n"
                "Step Time,U_Y,Total RF Y\n\n"
                "0.84,0.009,500\n"
                "0.85,0.010,523\n"
                "0.96,-0.009,-500\n"
            )
            context = self.module.frame_context_from_cycle_csv(csv_path, step_time=0.851)
        self.assertAlmostEqual(context.step_time, 0.85)
        self.assertAlmostEqual(context.global_strain, 0.010)
        self.assertAlmostEqual(context.global_stress, 523.0)

    def test_representative_roi_selection_uses_absolute_stress_magnitude(self):
        rows = [
            {"roi_name": "roi_left_01", "average_stress_mpa": -90.0, "average_plastic_strain": 0.010, "Phase 0": 25, "Phase 1": 25, "Phase 2": 25, "Phase 3": 25},
            {"roi_name": "roi_left_02", "average_stress_mpa": -130.0, "average_plastic_strain": 0.001, "Phase 0": 25, "Phase 1": 25, "Phase 2": 25, "Phase 3": 25},
            {"roi_name": "roi_right_01", "average_stress_mpa": -100.0, "average_plastic_strain": 0.005, "Phase 0": 25, "Phase 1": 25, "Phase 2": 25, "Phase 3": 25},
            {"roi_name": "roi_right_02", "average_stress_mpa": -85.0, "average_plastic_strain": 0.020, "Phase 0": 25, "Phase 1": 25, "Phase 2": 25, "Phase 3": 25},
        ]
        frame_data = pd.DataFrame(rows)
        selected = self.module.select_representative_rois(
            frame_data,
            global_stress=-110.0,
            global_plastic_strain=0.004,
        )
        self.assertEqual(selected.low_stress_high_plastic_roi, "roi_right_02")
        self.assertEqual(selected.high_stress_low_plastic_roi, "roi_left_02")
        self.assertGreater(selected.metrics.loc["roi_left_02", "stress_ratio"], 1.0)
        self.assertLess(selected.metrics.loc["roi_right_02", "stress_ratio"], 1.0)

    def test_frame_title_adds_at_strain_after_dash(self):
        title = self.module.build_frame_title("Full ROI response", frame_number=85, step_time=0.85, global_strain=0.01)
        self.assertEqual(title, "Full ROI response — at +1% strain")
        self.assertNotIn("Frame", title)
        self.assertNotIn("Step time", title)

    def test_frame_filename_stays_plain_without_strain_phrase(self):
        filename = self.module.build_frame_filename("frame85_grouped_by_side")
        self.assertEqual(filename, "frame85_grouped_by_side.png")

    def test_global_stress_intensity_factor_uses_global_stress_reference(self):
        global_sif = self.module.global_stress_intensity_factor(global_stress_mpa=-110.0)
        expected = 1.12 * -110.0 * math.sqrt(math.pi * 0.0001)
        self.assertAlmostEqual(global_sif, expected)

    def test_representative_comparison_panel_titles_match_requested_wording(self):
        frame_data = pd.DataFrame([
            {"roi_name": "roi_left_01", "average_stress_mpa": -90.0, "average_plastic_strain": 0.010, "Phase 0": 40, "Phase 1": 20, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_left_02", "average_stress_mpa": -130.0, "average_plastic_strain": 0.001, "Phase 0": 25, "Phase 1": 25, "Phase 2": 25, "Phase 3": 25},
            {"roi_name": "roi_right_01", "average_stress_mpa": -100.0, "average_plastic_strain": 0.005, "Phase 0": 20, "Phase 1": 40, "Phase 2": 20, "Phase 3": 20},
        ])
        context = self.module.FrameContext(frame_number=85, step_time=0.85, global_strain=0.01, global_stress=-110.0, global_plastic_strain=0.004)
        with tempfile.TemporaryDirectory() as tmp:
            captured = {}
            original_save = self.module._save_figure

            def keep_figure_open(fig, output_path):
                captured["fig"] = fig
                original_save(fig, output_path)

            self.module._save_figure = keep_figure_open
            try:
                self.module.plot_representative_comparison(frame_data, context, Path(tmp) / "representative.png")
                titles = [axis.get_title() for axis in captured["fig"].axes]
                self.assertIn("mechanical response relative to global response", titles)
                self.assertIn("Local volume fractions", titles)
            finally:
                self.module._save_figure = original_save

    def test_sif_volume_fraction_plot_is_created_for_each_ordering_mode(self):
        frame_data = pd.DataFrame([
            {"roi_name": "roi_left_01", "stress_intensity_factor": -1.0, "Phase 0": 40, "Phase 1": 20, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_right_01", "stress_intensity_factor": -1.2, "Phase 0": 20, "Phase 1": 40, "Phase 2": 20, "Phase 3": 20},
        ])
        context = self.module.FrameContext(frame_number=85, step_time=0.85, global_strain=0.01, global_stress=-110.0, global_plastic_strain=0.004)
        with tempfile.TemporaryDirectory() as tmp:
            side_path = self.module.plot_sif_volume_fraction_comparison(
                frame_data, context, Path(tmp) / "sif_side.png", mode="grouped_by_side"
            )
            height_path = self.module.plot_sif_volume_fraction_comparison(
                frame_data, context, Path(tmp) / "sif_height.png", mode="paired_by_height"
            )
        self.assertEqual(side_path.name, "sif_side.png")
        self.assertEqual(height_path.name, "sif_height.png")

    def test_grouped_sif_volume_fraction_uses_four_side_split_subpanels(self):
        frame_data = pd.DataFrame([
            {"roi_name": "roi_left_01", "stress_intensity_factor": -1.0, "Phase 0": 40, "Phase 1": 20, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_left_02", "stress_intensity_factor": -1.1, "Phase 0": 35, "Phase 1": 25, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_right_01", "stress_intensity_factor": -1.2, "Phase 0": 20, "Phase 1": 40, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_right_02", "stress_intensity_factor": -1.3, "Phase 0": 25, "Phase 1": 35, "Phase 2": 20, "Phase 3": 20},
        ])
        context = self.module.FrameContext(frame_number=85, step_time=0.85, global_strain=0.01, global_stress=-110.0, global_plastic_strain=0.004)
        with tempfile.TemporaryDirectory() as tmp:
            captured = {}
            original_save = self.module._save_figure

            def keep_figure_open(fig, output_path):
                captured["fig"] = fig
                original_save(fig, output_path)

            self.module._save_figure = keep_figure_open
            try:
                self.module.plot_sif_volume_fraction_comparison(frame_data, context, Path(tmp) / "sif_side.png", mode="grouped_by_side")
                axes = captured["fig"].axes
                self.assertEqual(len(axes), 4)
                self.assertEqual([axis.get_title() for axis in axes], ["Left ROI SIF", "Right ROI SIF", "Left ROI volume fractions", "Right ROI volume fractions"])
                self.assertTrue(all(axis.get_xlabel() == "" for axis in axes[2:]))
                self.assertTrue(all(len(axis.lines[0].get_xdata()) == 2 for axis in axes[:2]))
            finally:
                self.module._save_figure = original_save

    def test_phase_plot_groups_can_combine_equal_yield_phases(self):
        groups = self.module.phase_plot_groups(combine_equal_yield_phases=True)
        self.assertIn(("Phases 2+3", ["Phase 2", "Phase 3"], "#54A24B"), groups)
        self.assertNotIn(("Phase 2", ["Phase 2"], "#54A24B"), groups)

    def test_group_shading_can_hide_edge_labels_on_phase_panel(self):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        order = ["roi_left_01", "roi_left_02", "roi_right_01", "roi_right_02"]
        self.module._apply_group_shading(ax, order, mode="grouped_by_side", enabled=True, show_edge_labels=False)
        try:
            self.assertEqual([text.get_text() for text in ax.texts], [])
        finally:
            plt.close(fig)

    def test_grouped_by_side_shading_draws_middle_divider_between_left_and_right_rois(self):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        order = ["roi_left_01", "roi_left_02", "roi_right_01", "roi_right_02"]
        self.module._apply_group_shading(ax, order, mode="grouped_by_side", enabled=True)
        try:
            divider_x_positions = [line.get_xdata()[0] for line in ax.lines if line.get_linestyle() == "--"]
            self.assertIn(1.5, divider_x_positions)
        finally:
            plt.close(fig)

    def test_paired_by_height_shading_draws_dividers_between_two_roi_pairs(self):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        order = [
            "roi_left_01",
            "roi_right_01",
            "roi_left_02",
            "roi_right_02",
            "roi_left_03",
            "roi_right_03",
        ]
        self.module._apply_group_shading(ax, order, mode="paired_by_height", enabled=True)
        try:
            divider_x_positions = [line.get_xdata()[0] for line in ax.lines if line.get_linestyle() == "--"]
            self.assertEqual(divider_x_positions, [1.5, 3.5])
        finally:
            plt.close(fig)

    def test_paired_full_response_uses_points_without_connecting_lines(self):
        frame_data = pd.DataFrame([
            {"roi_name": "roi_left_01", "average_stress_mpa": -90.0, "average_plastic_strain": 0.010, "Phase 0": 40, "Phase 1": 20, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_right_01", "average_stress_mpa": -100.0, "average_plastic_strain": 0.005, "Phase 0": 20, "Phase 1": 40, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_left_02", "average_stress_mpa": -95.0, "average_plastic_strain": 0.012, "Phase 0": 35, "Phase 1": 25, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_right_02", "average_stress_mpa": -105.0, "average_plastic_strain": 0.006, "Phase 0": 25, "Phase 1": 35, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_left_03", "average_stress_mpa": -97.0, "average_plastic_strain": 0.014, "Phase 0": 30, "Phase 1": 30, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_right_03", "average_stress_mpa": -107.0, "average_plastic_strain": 0.007, "Phase 0": 28, "Phase 1": 32, "Phase 2": 20, "Phase 3": 20},
        ])
        context = self.module.FrameContext(frame_number=85, step_time=0.85, global_strain=0.01, global_stress=-110.0, global_plastic_strain=0.004)
        with tempfile.TemporaryDirectory() as tmp:
            captured = {}
            original_save = self.module._save_figure

            def keep_figure_open(fig, output_path):
                captured["fig"] = fig
                original_save(fig, output_path)

            self.module._save_figure = keep_figure_open
            try:
                self.module.plot_full_response(frame_data, context, Path(tmp) / "full.png", mode="paired_by_height")
                for axis in captured["fig"].axes[:2]:
                    roi_point_series = [line for line in axis.lines if line.get_marker() in {"o", "s"}]
                    self.assertTrue(roi_point_series)
                    self.assertTrue(all(line.get_linestyle() == "None" for line in roi_point_series))
            finally:
                self.module._save_figure = original_save

    def test_grouped_full_response_keeps_connected_lines(self):
        frame_data = pd.DataFrame([
            {"roi_name": "roi_left_01", "average_stress_mpa": -90.0, "average_plastic_strain": 0.010, "Phase 0": 40, "Phase 1": 20, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_left_02", "average_stress_mpa": -95.0, "average_plastic_strain": 0.012, "Phase 0": 35, "Phase 1": 25, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_right_01", "average_stress_mpa": -100.0, "average_plastic_strain": 0.005, "Phase 0": 20, "Phase 1": 40, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_right_02", "average_stress_mpa": -105.0, "average_plastic_strain": 0.006, "Phase 0": 25, "Phase 1": 35, "Phase 2": 20, "Phase 3": 20},
        ])
        context = self.module.FrameContext(frame_number=85, step_time=0.85, global_strain=0.01, global_stress=-110.0, global_plastic_strain=0.004)
        with tempfile.TemporaryDirectory() as tmp:
            captured = {}
            original_save = self.module._save_figure

            def keep_figure_open(fig, output_path):
                captured["fig"] = fig
                original_save(fig, output_path)

            self.module._save_figure = keep_figure_open
            try:
                self.module.plot_full_response(frame_data, context, Path(tmp) / "full.png", mode="grouped_by_side")
                for axis in captured["fig"].axes[:4]:
                    roi_series = [line for line in axis.lines if line.get_marker() in {"o", "s"}]
                    self.assertEqual(len(roi_series), 1)
                    self.assertEqual(roi_series[0].get_linestyle(), "-")
            finally:
                self.module._save_figure = original_save

    def test_full_response_uses_all_caps_roi_tick_labels_without_roi_axis_title(self):
        frame_data = pd.DataFrame([
            {"roi_name": "roi_left_01", "average_stress_mpa": -90.0, "average_plastic_strain": 0.010, "Phase 0": 40, "Phase 1": 20, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_right_01", "average_stress_mpa": -100.0, "average_plastic_strain": 0.005, "Phase 0": 20, "Phase 1": 40, "Phase 2": 20, "Phase 3": 20},
        ])
        context = self.module.FrameContext(frame_number=85, step_time=0.85, global_strain=0.01, global_stress=-110.0, global_plastic_strain=0.004)
        with tempfile.TemporaryDirectory() as tmp:
            captured = {}
            original_save = self.module._save_figure

            def keep_figure_open(fig, output_path):
                captured["fig"] = fig
                original_save(fig, output_path)

            self.module._save_figure = keep_figure_open
            try:
                self.module.plot_full_response(frame_data, context, Path(tmp) / "full.png", mode="grouped_by_side")
                self.assertEqual(captured["fig"].axes[-1].get_xlabel(), "")
                tick_labels = [tick.get_text() for tick in captured["fig"].axes[-1].get_xticklabels()]
                self.assertEqual(tick_labels, ["Right ROI 01"])
            finally:
                self.module._save_figure = original_save

    def test_grouped_full_response_uses_six_side_split_subpanels_with_volume_fractions(self):
        frame_data = pd.DataFrame([
            {"roi_name": "roi_left_01", "average_stress_mpa": -90.0, "average_plastic_strain": 0.010, "Phase 0": 40, "Phase 1": 20, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_left_02", "average_stress_mpa": -95.0, "average_plastic_strain": 0.012, "Phase 0": 35, "Phase 1": 25, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_right_01", "average_stress_mpa": -100.0, "average_plastic_strain": 0.005, "Phase 0": 20, "Phase 1": 40, "Phase 2": 20, "Phase 3": 20},
            {"roi_name": "roi_right_02", "average_stress_mpa": -105.0, "average_plastic_strain": 0.006, "Phase 0": 25, "Phase 1": 35, "Phase 2": 20, "Phase 3": 20},
        ])
        context = self.module.FrameContext(frame_number=85, step_time=0.85, global_strain=0.01, global_stress=-110.0, global_plastic_strain=0.004)
        with tempfile.TemporaryDirectory() as tmp:
            captured = {}
            original_save = self.module._save_figure

            def keep_figure_open(fig, output_path):
                captured["fig"] = fig
                original_save(fig, output_path)

            self.module._save_figure = keep_figure_open
            try:
                self.module.plot_full_response(frame_data, context, Path(tmp) / "full.png", mode="grouped_by_side")
                axes = captured["fig"].axes
                self.assertEqual(len(axes), 6)
                self.assertEqual(
                    [axis.get_title() for axis in axes],
                    [
                        "Left ROI stress",
                        "Right ROI stress",
                        "Left ROI plastic strain",
                        "Right ROI plastic strain",
                        "Left ROI volume fractions",
                        "Right ROI volume fractions",
                    ],
                )
                self.assertTrue(all(axis.get_xlabel() == "" for axis in axes[4:]))
                self.assertTrue(all(len(axis.lines[0].get_xdata()) == 2 for axis in axes[:4]))
                self.assertGreater(len(axes[4].patches), 0)
                self.assertGreater(len(axes[5].patches), 0)
            finally:
                self.module._save_figure = original_save

    def test_roi_plot_style_increases_fonts_and_uses_taller_slide_figures(self):
        self.assertEqual(self.module.ROI_FONT_SIZE_INCREASE_POINTS, 4)
        self.assertEqual(self.module.ROI_TITLE_FONTSIZE, 18)
        self.assertEqual(self.module.ROI_LOCATION_TITLE_FONTSIZE, 16)
        self.assertEqual(self.module.ROI_SMALL_ANNOTATION_FONTSIZE, 12)
        self.assertGreater(self.module.FULL_RESPONSE_GROUPED_FIGSIZE[1], 11.2)
        self.assertGreater(self.module.FULL_RESPONSE_PAIRED_FIGSIZE[1], 11.0)
        self.assertGreater(self.module.SIF_GROUPED_FIGSIZE[1], 8.4)
        self.assertGreater(self.module.SIF_PAIRED_FIGSIZE[1], 8.6)
        self.assertGreater(self.module.REPRESENTATIVE_FIGSIZE[1], 5.8)
        self.assertGreater(self.module.LOCATION_MAP_FIGSIZE[1], 7.2)

    def test_roi_location_uses_edge_half_circle_angles(self):
        self.assertEqual(self.module.roi_half_circle_angles("left"), (-90, 90))
        self.assertEqual(self.module.roi_half_circle_angles("right"), (90, 270))


if __name__ == "__main__":
    unittest.main()
