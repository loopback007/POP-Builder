from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB


db = SQLAlchemy()


class CatalogItem(db.Model):
    __tablename__ = "catalog_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    item_type = db.Column(db.String(40), nullable=False)  # chassis, line_card, management_device
    attributes = db.Column(JSONB, nullable=False, default=dict)
    unit_cost = db.Column(db.Float, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)


class Site(db.Model):
    __tablename__ = "sites"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    site_metadata = db.Column("metadata", JSONB, nullable=False, default=dict)
    chassis = db.relationship("Chassis", back_populates="site", cascade="all, delete-orphan")


class Chassis(db.Model):
    __tablename__ = "chassis"

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("sites.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    total_slots = db.Column(db.Integer, nullable=False)
    max_throughput_per_slot = db.Column(db.Float, nullable=False)
    base_cost = db.Column(db.Float, nullable=False, default=0)

    site = db.relationship("Site", back_populates="chassis")
    slots = db.relationship("Slot", back_populates="chassis", cascade="all, delete-orphan")


class Slot(db.Model):
    __tablename__ = "slots"

    id = db.Column(db.Integer, primary_key=True)
    chassis_id = db.Column(db.Integer, db.ForeignKey("chassis.id"), nullable=False)
    slot_index = db.Column(db.Integer, nullable=False)
    line_card_id = db.Column(db.Integer, db.ForeignKey("line_cards.id"))
    role_tag = db.Column(db.String(12), nullable=False, default="Dom")

    chassis = db.relationship("Chassis", back_populates="slots")
    line_card = db.relationship("LineCard", back_populates="slots")


class LineCard(db.Model):
    __tablename__ = "line_cards"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    port_count = db.Column(db.Integer, nullable=False)
    port_speed = db.Column(db.Integer, nullable=False)
    total_throughput = db.Column(db.Float, nullable=False)
    cost = db.Column(db.Float, nullable=False)
    attributes = db.Column(JSONB, nullable=False, default=dict)

    slots = db.relationship("Slot", back_populates="line_card")


class Port(db.Model):
    __tablename__ = "ports"

    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey("slots.id"), nullable=False)
    speed = db.Column(db.Integer, nullable=False)
    role_tag = db.Column(db.String(12), nullable=False, default="Dom")
    allocated = db.Column(db.Boolean, nullable=False, default=False)
