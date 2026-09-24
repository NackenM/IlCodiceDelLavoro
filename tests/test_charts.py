"""Every chart builds, including edge cases, and the step logic is right."""

import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

from job_tracker import charts
from job_tracker.charts.progress import shown_stages
from job_tracker.charts.statistics import company_share_slices
from job_tracker.charts.waterfall import waterfall_steps
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
    render(charts.build_timeline_figure(applications, TODAY))
    render(charts.build_company_outcomes_figure(applications, TODAY))
    render(charts.build_company_share_figure(applications))
    for target in SUCCESS_TARGETS:
        render(charts.build_success_rate_figure(applications, target, TODAY))


def test_timeline_of_an_application_without_dates_renders():
    render(charts.build_timeline_figure([make_application()], TODAY))


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
