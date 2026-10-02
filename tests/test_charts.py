"""Every chart builds, including edge cases, and the step logic is right."""

import pytest
from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.dates import date2num

from job_tracker import charts
from job_tracker.charts.progress import LEGEND_MAX_APPLICATIONS, shown_stages
from job_tracker.charts.statistics import company_share_slices
from job_tracker.charts.style import bullet_list
from job_tracker.charts.timeline import row_label
from job_tracker.charts.waterfall import waterfall_steps
from job_tracker.logos import initials_tile
from job_tracker.model import NO_COMPANY
from job_tracker.outcomes import SUCCESS_TARGETS
from job_tracker.stages import Stage

from .factories import TODAY, make_application

SAMPLE = [
    make_application(
        company="Acme",
        dates={
            Stage.APPLIED: "2026-07-01",
            Stage.ROUND_1: "2026-07-08",
            Stage.CODING_CHALLENGE: "2026-07-10",
            Stage.ROUND_2: "2026-07-15",
            Stage.OFFER: "2026-07-25",
        },
    ),
    make_application(
        company="Globex",
        dates={
            Stage.APPLIED: "2026-07-05",
            Stage.ROUND_1: "2026-07-12",
            Stage.REJECTED: "2026-07-20",
        },
    ),
    make_application(company="Acme", dates={Stage.APPLIED: "2026-09-20"}),
    make_application(company="", dates={Stage.APPLIED: "2026-06-01"}),
]


def render(figure):
    FigureCanvasAgg(figure).draw()


@pytest.mark.parametrize("applications", [SAMPLE, SAMPLE[:1], []])
def test_every_chart_renders(applications):
    render(charts.build_outcome_waterfall_figure(applications, TODAY))
    render(charts.build_progress_figure(applications))
    timeline = charts.build_timeline_figures(applications, TODAY)
    render(timeline.header)
    render(timeline.body)
    render(charts.build_company_outcomes_figure(applications, TODAY))
    render(charts.build_company_share_figure(applications))
    render(charts.build_reply_times_figure(applications, TODAY))
    for target in SUCCESS_TARGETS:
        render(charts.build_success_rate_figure(applications, target, TODAY))


def test_timeline_of_an_application_without_dates_renders():
    timeline = charts.build_timeline_figures([make_application()], TODAY)
    render(timeline.header)
    render(timeline.body)


def test_waterfall_has_a_step_for_every_round_even_at_zero():
    labels = [step.label for step in waterfall_steps(SAMPLE, TODAY)]
    assert labels == [
        "Applications",
        "Ghosted",
        "Rejected\nright away",
        "Rejected after\n1st Round",
        "Rejected after\n2nd Round",
        "Rejected after\n3rd Round",
        "In progress",
        "Offers",
    ]


def test_waterfall_steps_add_up():
    steps = waterfall_steps(SAMPLE, TODAY)
    total, *subtracted, offers = steps
    assert total.count - sum(step.count for step in subtracted) == offers.count


def test_waterfall_shows_the_online_assessment_once_used():
    with_assessment = [
        *SAMPLE,
        make_application(
            dates={
                Stage.APPLIED: "2026-09-01",
                Stage.ONLINE_ASSESSMENT: "2026-09-03",
                Stage.REJECTED: "2026-09-05",
            }
        ),
    ]
    steps = waterfall_steps(with_assessment, TODAY)
    (assessment_step,) = [s for s in steps if "Assessment" in s.label]
    assert assessment_step.count == 1


def test_progress_hides_an_unused_online_assessment():
    assert Stage.ONLINE_ASSESSMENT not in shown_stages(SAMPLE)
    used = make_application(dates={Stage.ONLINE_ASSESSMENT: "2026-09-01"})
    assert Stage.ONLINE_ASSESSMENT in shown_stages([*SAMPLE, used])


def test_company_share_folds_small_companies_into_other():
    applications = [
        make_application(company=f"Company {index}") for index in range(5)
    ] + [make_application(company="")]
    slices = company_share_slices(applications, max_slices=2)
    assert [s.label for s in slices] == [
        "Company 0",
        "Company 1",
        "Other (3 companies)",
        NO_COMPANY,
    ]
    assert sum(s.count for s in slices) == len(applications)


def test_company_share_names_a_single_leftover_company():
    applications = [
        make_application(company=f"C{index}") for index in range(3)
    ]
    slices = company_share_slices(applications, max_slices=2)
    assert [s.label for s in slices] == ["C0", "C1", "C2"]


def _applications(count):
    return [
        make_application(id=str(index), dates={Stage.APPLIED: "2026-09-01"})
        for index in range(count)
    ]


def test_progress_legend_names_up_to_the_limit():
    figure = charts.build_progress_figure(
        _applications(LEGEND_MAX_APPLICATIONS)
    )
    (axes,) = figure.axes
    legend = axes.get_legend()
    assert len(legend.get_texts()) == LEGEND_MAX_APPLICATIONS


def test_progress_legend_is_left_out_past_the_limit():
    figure = charts.build_progress_figure(
        _applications(LEGEND_MAX_APPLICATIONS + 1)
    )
    (axes,) = figure.axes
    assert axes.get_legend() is None


def test_bullet_list_counts_what_it_leaves_out():
    assert bullet_list(["a", "b"], max_entries=3) == "• a\n• b"
    assert bullet_list(["a", "b", "c", "d"], max_entries=2) == (
        "• a\n• b\n… and 2 more"
    )


def test_timeline_row_label_puts_the_title_under_the_company():
    application = make_application(
        company="Acme Robotics",
        job_title="Senior Embedded Software Engineer for Robot Perception",
    )
    assert row_label(application) == (
        "Acme Robotics\nSenior Embedded Software\nEngineer for Robot…"
    )


def test_timeline_row_label_falls_back_to_the_id():
    assert (
        row_label(make_application(id="ab12", company="", job_title=""))
        == "ab12"
    )


def test_hover_shows_and_hides_the_tooltip():
    figure = charts.build_timeline_figures(SAMPLE[:1], TODAY).body
    canvas = FigureCanvasAgg(figure)
    canvas.draw()
    (axes,) = figure.axes
    (marker, *_) = [line for line in axes.lines if line.get_marker() == "o"]
    x, y = axes.transData.transform(
        (date2num(marker.get_xdata()[0]), marker.get_ydata()[0])
    )
    tooltip = next(t for t in axes.texts if t.get_animated())

    MouseEvent("motion_notify_event", canvas, x, y)._process()
    assert tooltip.get_visible()
    assert tooltip.get_text() == "01.07.2026\nApplied"

    MouseEvent("motion_notify_event", canvas, 1, 1)._process()
    assert not tooltip.get_visible()


def test_timeline_header_dates_line_up_with_the_rows_below():
    timeline = charts.build_timeline_figures(SAMPLE, TODAY)
    FigureCanvasAgg(timeline.header)
    render(timeline.body)  # lays the body out, which lines the header up
    (header_axes,) = timeline.header.axes
    (body_axes,) = timeline.body.axes
    assert header_axes.get_xlim() == body_axes.get_xlim()
    assert header_axes.bbox.x0 == pytest.approx(body_axes.bbox.x0)
    assert header_axes.bbox.x1 == pytest.approx(body_axes.bbox.x1)


def test_charts_render_with_company_logos():
    timeline = charts.build_timeline_figures(
        SAMPLE, TODAY, logos=initials_tile
    )
    render(timeline.header)
    render(timeline.body)
    render(
        charts.build_company_outcomes_figure(
            SAMPLE, TODAY, logos=initials_tile
        )
    )


def _subtitle(figure):
    (axes,) = figure.axes
    texts = [text.get_text() for text in axes.texts]
    return next(text for text in texts if text.startswith("■"))


@pytest.mark.parametrize("picked", SAMPLE)
def test_waterfall_names_the_highlighted_application(picked):
    figure = charts.build_outcome_waterfall_figure(
        SAMPLE, TODAY, highlight=picked
    )
    render(figure)
    assert _subtitle(figure).startswith(f"■ {picked.display_name}  →  ")


def test_waterfall_highlight_names_where_it_ended():
    rejected = SAMPLE[1]  # rejected after the 1st round
    figure = charts.build_outcome_waterfall_figure(
        SAMPLE, TODAY, highlight=rejected
    )
    assert _subtitle(figure).endswith("→  Rejected after 1st Round")


def test_progress_outlines_only_the_highlighted_application():
    picked = SAMPLE[0]
    figure = charts.build_progress_figure(SAMPLE, highlight=picked)
    render(figure)
    (axes,) = figure.axes
    outlined = [p for p in axes.patches if p.get_linewidth() == 2]
    assert len(outlined) == sum(picked.has_reached(stage) for stage in Stage)
    assert _subtitle(figure) == (
        f"■ {picked.display_name}  →  {picked.status_label()}"
    )
