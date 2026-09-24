"""CSV storage and the one-time legacy migration."""

import csv
from datetime import date

import pytest

from job_tracker.csv_columns import ALL_COLUMNS
from job_tracker.legacy_migration import has_legacy_columns, migrate_row
from job_tracker.model import RoundTags
from job_tracker.repository import (
    LEGACY_BACKUP_SUFFIX,
    ApplicationNotFoundError,
    ApplicationRepository,
    application_from_row,
    application_to_row,
)
from job_tracker.stages import RoundFocus, RoundFormat, Stage

from .factories import TODAY, make_application


@pytest.fixture
def csv_path(tmp_path):
    return tmp_path / "data" / "applications.csv"


@pytest.fixture
def repository(csv_path):
    return ApplicationRepository(csv_path, today=lambda: TODAY)


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_missing_file_means_no_applications(repository):
    assert repository.load_all() == []


def test_add_update_delete(repository, csv_path):
    added = repository.add(
        make_application(job_title="Dev", dates={Stage.APPLIED: "2026-09-01"})
    )
    assert added.last_update == TODAY
    assert csv_path.exists()
    assert repository.load_all() == [added]

    added.job_title = "Senior Dev"
    added.stage_dates[Stage.ROUND_1] = date(2026, 9, 10)
    repository.update(added)
    (reloaded,) = repository.load_all()
    assert reloaded.job_title == "Senior Dev"
    assert reloaded.stage_dates[Stage.ROUND_1] == date(2026, 9, 10)

    repository.delete(added.id)
    assert repository.load_all() == []


def test_unknown_id(repository):
    with pytest.raises(ApplicationNotFoundError):
        repository.delete("nope")
    with pytest.raises(ApplicationNotFoundError):
        repository.update(make_application())


def test_every_field_survives_a_round_trip(repository):
    application = make_application(
        company="Acme, Inc.",  # comma and quotes need CSV quoting
        job_title='Dev "Platform"',
        status=Stage.ROUND_2,
        dates={
            stage: f"2026-09-{day:02d}"
            for day, stage in enumerate(Stage, start=1)
        },
        tags={
            Stage.ROUND_1: RoundTags(RoundFormat.PHONE, RoundFocus.HR),
            Stage.ROUND_2: RoundTags(focus=RoundFocus.TECHNICAL),
        },
        contact_email="a@x.example",
        url="https://jobs.example/1",
        job_description="Line one\nLine two",
        salary="65-75k €",
        notes="Referral",
    )
    saved = repository.add(application)
    assert repository.load_all() == [saved]


def test_file_uses_the_documented_columns(repository, csv_path):
    repository.add(make_application())
    with csv_path.open(encoding="utf-8") as file:
        assert file.readline().rstrip("\n").split(",") == ALL_COLUMNS


def test_row_conversion_tolerates_bad_values():
    application = application_from_row(
        {
            "id": "x1",
            "status": "Something old",
            "date_applied": "2026-09-01",
            "date_round_1": "not a date",
            "date_round_2": "2026-09-10",
            "round_2_format": "Carrier pigeon",
            "round_2_focus": "HR",
        }
    )
    # Unknown status: the furthest stage reached instead.
    assert application.status is Stage.ROUND_2
    assert Stage.ROUND_1 not in application.stage_dates
    assert application.tags_of(Stage.ROUND_2) == RoundTags(focus=RoundFocus.HR)


def test_row_conversion_writes_blank_for_unset_values():
    row = application_to_row(make_application())
    assert row["date_offer"] == ""
    assert row["round_1_format"] == ""
    assert row["last_update"] == ""


class TestLegacyMigration:
    LEGACY_COLUMNS = [
        "id",
        "job_title",
        "company",
        "status",
        "notes",
        "date_applied",
        "date_interview_initial",
        "date_interview_virtual",
        "date_interview_2nd",
        "date_interview_3rd",
        "date_interview_onsite",
        "date_coding_challenge",
    ]

    def legacy_row(self, **values):
        return {column: "" for column in self.LEGACY_COLUMNS} | values

    def test_detects_legacy_columns(self):
        assert has_legacy_columns(self.LEGACY_COLUMNS)
        assert not has_legacy_columns(ALL_COLUMNS)

    def test_interviews_become_rounds_in_date_order(self):
        migrated = migrate_row(
            self.legacy_row(
                status="Interview - On-site",
                date_interview_initial="2026-07-01",
                date_interview_onsite="2026-07-20",
                date_interview_virtual="2026-07-10",
            )
        )
        assert migrated["date_round_1"] == "2026-07-01"
        assert migrated["round_1_format"] == ""
        assert migrated["date_round_2"] == "2026-07-10"
        assert migrated["round_2_format"] == "Virtual"
        assert migrated["date_round_3"] == "2026-07-20"
        assert migrated["round_3_format"] == "On-site"
        assert migrated["status"] == Stage.ROUND_3
        assert "date_interview_initial" not in migrated

    def test_same_day_interviews_keep_the_old_stage_order(self):
        migrated = migrate_row(
            self.legacy_row(
                date_interview_onsite="2026-07-01",
                date_interview_initial="2026-07-01",
            )
        )
        assert migrated["round_1_format"] == ""
        assert migrated["round_2_format"] == "On-site"

    def test_more_than_three_interviews_go_to_the_notes(self):
        migrated = migrate_row(
            self.legacy_row(
                notes="Nice team",
                date_interview_initial="2026-07-01",
                date_interview_virtual="2026-07-02",
                date_interview_2nd="2026-07-03",
                date_interview_3rd="2026-07-04",
            )
        )
        assert migrated["date_round_3"] == "2026-07-03"
        assert migrated["notes"] == (
            "Nice team | Further interviews: Interview - 3rd Round 2026-07-04"
        )

    def test_status_without_a_date_goes_to_the_furthest_round(self):
        migrated = migrate_row(
            self.legacy_row(
                status="Interview - 3rd Round",
                date_interview_initial="2026-07-01",
            )
        )
        assert migrated["status"] == Stage.ROUND_1

    def test_other_statuses_are_kept(self):
        migrated = migrate_row(self.legacy_row(status="Coding Challenge"))
        assert migrated["status"] == "Coding Challenge"

    def test_legacy_file_is_migrated_once_with_a_backup(
        self, repository, csv_path
    ):
        write_csv(
            csv_path,
            [
                self.legacy_row(
                    id="a1",
                    status="Interview - Virtual",
                    date_applied="2026-07-01",
                    date_interview_virtual="2026-07-10",
                )
            ],
            self.LEGACY_COLUMNS,
        )
        original = csv_path.read_bytes()

        (application,) = repository.load_all()
        assert application.status is Stage.ROUND_1
        assert application.tags_of(Stage.ROUND_1).format is RoundFormat.VIRTUAL

        backup = csv_path.with_name(csv_path.stem + LEGACY_BACKUP_SUFFIX)
        assert backup.read_bytes() == original
        assert list(read_csv(csv_path)[0]) == ALL_COLUMNS

        # Loading again finds nothing left to migrate.
        rewritten = csv_path.read_bytes()
        assert repository.load_all() == [application]
        assert csv_path.read_bytes() == rewritten
