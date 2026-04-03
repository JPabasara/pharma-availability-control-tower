import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.orchestration import service as orchestration_service
from apps.api.app.planner_flow import service as planner_service
from storage.models import (
    AuditLog,
    Base,
    DC,
    EngineRun,
    Lorry,
    M2Request,
    M3PlanItem,
    M3PlanRun,
    M3PlanStop,
    M3PlanVersion,
    PlannerDecision,
    SKU,
)


class SingletonLivePlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.session = self.SessionLocal()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _seed_master_data(self) -> tuple[SKU, DC, Lorry]:
        sku = SKU(
            code="SKU-1",
            name="Cold Med",
            category="critical",
            reefer_required=False,
            unit_weight_kg=1.0,
            unit_volume_m3=1.0,
        )
        dc = DC(
            code="DC-1",
            name="Main DC",
            region="West",
            latitude=0.0,
            longitude=0.0,
        )
        lorry = Lorry(
            registration="WP-1234",
            lorry_type="normal",
            capacity_units=100,
            status="available",
        )
        self.session.add_all([sku, dc, lorry])
        self.session.commit()
        return sku, dc, lorry

    def _create_plan(
        self,
        engine_run: EngineRun,
        sku: SKU,
        dc: DC,
        lorry: Lorry,
        *,
        version_number: int,
        plan_status: str = "draft",
        days: tuple[int, ...] = (1, 2),
    ) -> M3PlanVersion:
        plan = M3PlanVersion(
            engine_run_id=engine_run.id,
            version_number=version_number,
            plan_status=plan_status,
            score=10.0 + version_number,
            is_best=version_number == 1,
        )
        self.session.add(plan)
        self.session.flush()

        for dispatch_day in days:
            run = M3PlanRun(
                plan_version_id=plan.id,
                lorry_id=lorry.id,
                dispatch_day=dispatch_day,
            )
            self.session.add(run)
            self.session.flush()

            stop = M3PlanStop(
                plan_run_id=run.id,
                stop_sequence=1,
                dc_id=dc.id,
            )
            self.session.add(stop)
            self.session.flush()

            self.session.add(
                M3PlanItem(
                    plan_stop_id=stop.id,
                    sku_id=sku.id,
                    quantity=10 * dispatch_day,
                )
            )

        self.session.commit()
        return plan

    def test_refresh_m2_replaces_previous_singleton_results(self) -> None:
        sku, dc, _ = self._seed_master_data()

        m2_outputs = [
            [
                {
                    "dc_id": dc.id,
                    "sku_id": sku.id,
                    "requested_quantity": 5,
                    "urgency": "high",
                    "required_by": "2026-04-04T00:00:00+00:00",
                }
            ],
            [
                {
                    "dc_id": dc.id,
                    "sku_id": sku.id,
                    "requested_quantity": 12,
                    "urgency": "critical",
                    "required_by": "2026-04-05T00:00:00+00:00",
                }
            ],
        ]

        with patch("apps.api.app.orchestration.service.dc_reader.get_all_latest_contracts", return_value=[{"snapshot_id": 1}]), patch(
            "apps.api.app.orchestration.service.sales_reader.to_contract",
            return_value=[],
        ), patch("apps.api.app.orchestration.service.engine_bridge.get_engine_mode", return_value="stub"), patch(
            "apps.api.app.orchestration.service.engine_bridge.run_m2",
            side_effect=m2_outputs,
        ):
            orchestration_service.refresh_m2(self.session)
            orchestration_service.refresh_m2(self.session)

        runs = self.session.query(EngineRun).filter(EngineRun.engine_type == "m2").all()
        requests = self.session.query(M2Request).all()
        self.assertEqual(len(runs), 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].requested_quantity, 12)
        self.assertEqual(requests[0].urgency, "critical")

    def test_override_updates_current_draft_in_place(self) -> None:
        sku, dc, lorry = self._seed_master_data()
        engine_run = EngineRun(
            engine_type="m3",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            status="completed",
            planning_start_date=orchestration_service.get_current_planning_start_date(),
        )
        self.session.add(engine_run)
        self.session.commit()
        plan = self._create_plan(engine_run, sku, dc, lorry, version_number=1)

        changes = [
            {
                "lorry_id": lorry.id,
                "dispatch_day": 1,
                "stops": [
                    {
                        "dc_id": dc.id,
                        "stop_sequence": 1,
                        "items": [{"sku_id": sku.id, "quantity": 25}],
                    }
                ],
            }
        ]

        with patch("apps.api.app.planner_flow.service.validate_override", return_value={"valid": True, "errors": [], "warnings": []}):
            result = planner_service.override_plan(self.session, plan.id, changes, notes="Manual edit")

        self.assertTrue(result["success"])
        self.assertEqual(result["new_plan_version_id"], plan.id)
        self.assertEqual(self.session.query(M3PlanVersion).count(), 1)

        refreshed = (
            self.session.query(M3PlanVersion)
            .filter(M3PlanVersion.id == plan.id)
            .first()
        )
        self.assertFalse(refreshed.is_best)
        runs = self.session.query(M3PlanRun).filter(M3PlanRun.plan_version_id == plan.id).all()
        items = (
            self.session.query(M3PlanItem)
            .join(M3PlanStop, M3PlanItem.plan_stop_id == M3PlanStop.id)
            .join(M3PlanRun, M3PlanStop.plan_run_id == M3PlanRun.id)
            .filter(M3PlanRun.plan_version_id == plan.id)
            .all()
        )
        self.assertEqual(len(runs), 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].quantity, 25)
        self.assertEqual(self.session.query(PlannerDecision).filter(PlannerDecision.decision_type == "override").count(), 1)
        self.assertEqual(self.session.query(AuditLog).filter(AuditLog.action == "overridden").count(), 1)

    def test_reject_archives_selected_plan_and_regenerates_singleton_set(self) -> None:
        sku, dc, lorry = self._seed_master_data()
        old_run = EngineRun(
            engine_type="m3",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            completed_at=datetime.now(timezone.utc) - timedelta(minutes=4),
            status="completed",
            planning_start_date=orchestration_service.get_current_planning_start_date(),
        )
        self.session.add(old_run)
        self.session.commit()
        rejected_plan = self._create_plan(old_run, sku, dc, lorry, version_number=1)
        self._create_plan(old_run, sku, dc, lorry, version_number=2)
        self._create_plan(old_run, sku, dc, lorry, version_number=3)

        def fake_generate_plan(session):
            orchestration_service.purge_live_m3_drafts(session)
            new_run = EngineRun(
                engine_type="m3",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                status="completed",
                planning_start_date=orchestration_service.get_current_planning_start_date(),
            )
            session.add(new_run)
            session.flush()
            new_plan = M3PlanVersion(
                engine_run_id=new_run.id,
                version_number=1,
                plan_status="draft",
                score=99.0,
                is_best=True,
            )
            session.add(new_plan)
            session.commit()
            return {"m3_plans_count": 1}

        with patch("apps.api.app.planner_flow.service.orchestration_service.generate_plan", side_effect=fake_generate_plan):
            result = planner_service.reject_plan(self.session, rejected_plan.id, notes="Not workable")

        self.assertTrue(result["success"])
        self.assertEqual(self.session.query(M3PlanVersion).filter(M3PlanVersion.plan_status == "draft").count(), 1)
        self.assertEqual(self.session.query(M3PlanVersion).filter(M3PlanVersion.plan_status == "rejected").count(), 1)
        self.assertEqual(
            self.session.query(M3PlanVersion).filter(M3PlanVersion.id == rejected_plan.id).first().plan_status,
            "rejected",
        )

    def test_lock_is_scoped_to_current_planning_horizon(self) -> None:
        sku, dc, lorry = self._seed_master_data()
        current_start = orchestration_service.get_current_planning_start_date()

        old_run = EngineRun(
            engine_type="m3",
            started_at=datetime.now(timezone.utc) - timedelta(days=1),
            completed_at=datetime.now(timezone.utc) - timedelta(days=1),
            status="completed",
            planning_start_date=current_start - timedelta(days=1),
        )
        self.session.add(old_run)
        self.session.commit()
        self._create_plan(old_run, sku, dc, lorry, version_number=1, plan_status="approved")

        self.assertFalse(orchestration_service.get_m3_lock_state(self.session)["locked"])

        current_run = EngineRun(
            engine_type="m3",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            status="completed",
            planning_start_date=current_start,
        )
        self.session.add(current_run)
        self.session.commit()
        self._create_plan(current_run, sku, dc, lorry, version_number=1, plan_status="approved")

        lock_state = orchestration_service.get_m3_lock_state(self.session)
        self.assertTrue(lock_state["locked"])
        self.assertIn(str(current_start.year), lock_state["lock_reason"])


if __name__ == "__main__":
    unittest.main()
