from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Dict, List

from models import CatalogItem, Chassis, LineCard, Site, Slot


@dataclass
class Requirement:
    throughput_gbps: float
    port_speed: int
    port_count: int
    role: str


class PoPSolver:
    def __init__(self, site: Site, strategy: str, forecast_gbps: float, dispersion_intl: float, port_requirements: List[Requirement]):
        self.site = site
        self.strategy = strategy
        self.forecast_gbps = forecast_gbps
        self.dispersion_intl = dispersion_intl
        self.dispersion_dom = 100 - dispersion_intl
        self.port_requirements = port_requirements

    def normalize_demand(self) -> float:
        if self.strategy.upper() == "N+1":
            return self.forecast_gbps * 2
        return self.forecast_gbps / 0.95

    def current_capacity(self) -> Dict[str, Dict[str, float]]:
        caps = {
            "Intl": {"throughput": 0.0, "ports": 0},
            "Dom": {"throughput": 0.0, "ports": 0},
        }
        for chassis in self.site.chassis:
            for slot in chassis.slots:
                if slot.line_card is None:
                    continue
                role = slot.role_tag if slot.role_tag in caps else "Dom"
                caps[role]["throughput"] += slot.line_card.total_throughput
                caps[role]["ports"] += slot.line_card.port_count
        return caps

    def _find_cheapest_linecard(self, role: str, speed: int, min_throughput: float) -> LineCard | None:
        q = (
            LineCard.query.filter(LineCard.port_speed >= speed)
            .filter(LineCard.total_throughput >= min_throughput)
            .order_by(LineCard.cost.asc())
        )
        return q.first()

    def _find_compatible_chassis_slot(self, line_card: LineCard) -> Slot | None:
        for chassis in self.site.chassis:
            if line_card.total_throughput > chassis.max_throughput_per_slot:
                continue
            for slot in chassis.slots:
                if slot.line_card_id is None:
                    return slot
        return None

    def _build_chassis_from_catalog(self, role: str) -> Chassis:
        chassis_item = (
            CatalogItem.query.filter_by(item_type="chassis", active=True).order_by(CatalogItem.unit_cost.asc()).first()
        )
        if not chassis_item:
            raise ValueError("No chassis available in catalog")

        attrs = chassis_item.attributes
        new_chassis = Chassis(
            site_id=self.site.id,
            name=f"{self.site.name}-Expansion-{len(self.site.chassis)+1}",
            total_slots=int(attrs.get("total_slots", 8)),
            max_throughput_per_slot=float(attrs.get("max_throughput_per_slot", 800)),
            base_cost=chassis_item.unit_cost,
        )

        for idx in range(1, new_chassis.total_slots + 1):
            new_chassis.slots.append(Slot(slot_index=idx, role_tag=role))
        return new_chassis

    def solve(self):
        effective_demand = self.normalize_demand()
        needed = {
            "Intl": effective_demand * (self.dispersion_intl / 100),
            "Dom": effective_demand * (self.dispersion_dom / 100),
        }
        current = self.current_capacity()
        baseline = {
            "Intl": current["Intl"].copy(),
            "Dom": current["Dom"].copy(),
        }

        bom = []

        for role in ["Intl", "Dom"]:
            throughput_deficit = max(0.0, needed[role] - current[role]["throughput"])
            role_requirements = [r for r in self.port_requirements if r.role == role]
            port_deficit = sum(max(0, r.port_count - current[role]["ports"]) for r in role_requirements)

            while throughput_deficit > 0 or port_deficit > 0:
                speed = max([r.port_speed for r in role_requirements], default=100)
                min_tput = max(throughput_deficit, speed)
                card = self._find_cheapest_linecard(role, speed, min_tput)
                if card is None:
                    raise ValueError(f"No compatible line card for role {role} and speed {speed}")

                slot = self._find_compatible_chassis_slot(card)
                if slot is None:
                    new_chassis = self._build_chassis_from_catalog(role)
                    self.site.chassis.append(new_chassis)
                    mgmt = (
                        CatalogItem.query.filter_by(item_type="management_device", active=True)
                        .order_by(CatalogItem.unit_cost.asc())
                        .first()
                    )
                    bom.append({"item": new_chassis.name, "type": "Chassis", "qty": 1, "unit_cost": new_chassis.base_cost})
                    if mgmt:
                        bom.append(
                            {
                                "item": mgmt.name,
                                "type": "Management Device",
                                "qty": 1,
                                "unit_cost": mgmt.unit_cost,
                            }
                        )
                    slot = new_chassis.slots[0]

                slot.line_card = card
                bom.append({"item": card.name, "type": "Line Card", "qty": 1, "unit_cost": card.cost})

                current[role]["throughput"] += card.total_throughput
                current[role]["ports"] += card.port_count
                throughput_deficit = max(0.0, needed[role] - current[role]["throughput"])
                if role_requirements:
                    required_ports = sum(r.port_count for r in role_requirements)
                    port_deficit = max(0, required_ports - current[role]["ports"])
                else:
                    port_deficit = 0

        bom_summary = []
        grouped = {}
        for row in bom:
            key = (row["item"], row["type"], row["unit_cost"])
            grouped[key] = grouped.get(key, 0) + row["qty"]

        total_cost = 0.0
        for (item, row_type, unit_cost), qty in grouped.items():
            line_total = qty * unit_cost
            total_cost += line_total
            bom_summary.append(
                {
                    "item": item,
                    "type": row_type,
                    "qty": qty,
                    "unit_cost": unit_cost,
                    "total_cost": line_total,
                }
            )

        post_state = []
        for chassis in self.site.chassis:
            occupied = len([s for s in chassis.slots if s.line_card_id is not None or s.line_card is not None])
            post_state.append(f"{chassis.name}: {occupied}/{chassis.total_slots} slots occupied")

        return {
            "effective_demand": ceil(effective_demand),
            "needed": needed,
            "baseline": baseline,
            "current": current,
            "bom": bom_summary,
            "total_cost": total_cost,
            "post_state": post_state,
        }
