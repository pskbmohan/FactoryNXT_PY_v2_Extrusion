from flask import Blueprint, jsonify
from ..models import Line

bp = Blueprint("api", __name__)


@bp.get("/status")
def status():
    lines = Line.query.all()
    return jsonify(
        {
            "lines": [
                {"id": line.id, "name": line.name, "status": line.status}
                for line in lines
            ]
        }
    )
