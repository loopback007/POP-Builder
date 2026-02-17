import csv
import io
import os

from flask import Flask, Response, flash, redirect, render_template, request, session, url_for
from redis import Redis
from rq import Queue

from logic import PoPSolver, Requirement
from models import CatalogItem, Chassis, LineCard, Site, Slot, db


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    f"postgresql://{os.getenv('POSTGRES_USER', 'popuser')}:{os.getenv('POSTGRES_PASSWORD', 'poppass')}@localhost:5432/{os.getenv('POSTGRES_DB', 'popbuilder')}",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db.init_app(app)

redis_conn = Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", "6379")), db=0)
queue = Queue("pop-jobs", connection=redis_conn)


@app.before_request
def init_data():
    db.create_all()
    if CatalogItem.query.count() == 0:
        db.session.add_all(
            [
                CatalogItem(
                    name="Modular Chassis X8",
                    item_type="chassis",
                    unit_cost=48000,
                    attributes={"total_slots": 8, "max_throughput_per_slot": 800},
                ),
                CatalogItem(name="OOB Switch 48", item_type="management_device", unit_cost=3000, attributes={"model": "OOB-48"}),
            ]
        )
    if LineCard.query.count() == 0:
        db.session.add_all(
            [
                LineCard(name="LC-100G-8P", port_count=8, port_speed=100, total_throughput=800, cost=12000),
                LineCard(name="LC-400G-4P", port_count=4, port_speed=400, total_throughput=1600, cost=19000),
                LineCard(name="LC-100G-4P", port_count=4, port_speed=100, total_throughput=400, cost=7000),
            ]
        )
    if Site.query.count() == 0:
        site = Site(name="Site-A")
        ch = Chassis(name="Router-A", total_slots=4, max_throughput_per_slot=800, base_cost=32000)
        for idx in range(1, 5):
            ch.slots.append(Slot(slot_index=idx, role_tag="Intl" if idx == 1 else "Dom"))
        ch.slots[0].line_card = LineCard.query.filter_by(name="LC-100G-4P").first()
        site.chassis.append(ch)
        db.session.add(site)
    db.session.commit()


@app.route("/", methods=["GET", "POST"])
def index():
    site = Site.query.first()
    result = session.get("latest_result")

    if request.method == "POST":
        try:
            forecast_gbps = float(request.form["forecast_gbps"])
            intl_split = float(request.form["intl_split"])
            strategy = request.form["strategy"]
            req_speed = int(request.form["req_speed"])
            req_count = int(request.form["req_count"])
            req_role = request.form["req_role"]

            requirements = [Requirement(throughput_gbps=req_speed * req_count, port_speed=req_speed, port_count=req_count, role=req_role)]
            solver = PoPSolver(
                site=site,
                strategy=strategy,
                forecast_gbps=forecast_gbps,
                dispersion_intl=intl_split,
                port_requirements=requirements,
            )
            result = solver.solve()
            session["latest_result"] = result
            db.session.commit()
            flash("Capacity plan generated successfully.", "success")
            return redirect(url_for("index"))
        except Exception as exc:
            db.session.rollback()
            flash(f"Calculation failed: {exc}", "danger")

    return render_template("index.html", site=site, result=result)


@app.route("/export.csv")
def export_csv():
    result = session.get("latest_result")
    if not result:
        return redirect(url_for("index"))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Section", "Item", "Type", "Qty", "Unit Cost", "Total Cost"])
    for row in result["bom"]:
        writer.writerow(["BOM", row["item"], row["type"], row["qty"], row["unit_cost"], row["total_cost"]])
    writer.writerow(["Summary", "Total Cost", "", "", "", result["total_cost"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=pop_upgrade_summary.csv"},
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
