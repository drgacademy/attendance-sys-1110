from flask import Blueprint, request, jsonify, abort
from services.people_service import PeopleService
from utils.helpers import ok, row_to_dict

people_bp = Blueprint("people", __name__, url_prefix="/api/people")


@people_bp.route("", methods=["GET"])
def list_people():
    people = PeopleService.list_all()
    return jsonify(people)


@people_bp.route("", methods=["POST"])
def create_person():
    payload_json = request.get_json(silent=True)
    data = PeopleService.parse_people_payload(request.files, payload_json)
    PeopleService.create(data)
    return ok(status=201)


@people_bp.route("/<ident>", methods=["GET"])
def get_person(ident):
    person = PeopleService.get_by_ident(ident)
    if not person:
        abort(404, "Person not found")
    return jsonify(row_to_dict(person))


@people_bp.route("/<ident>", methods=["PUT"])
def update_person(ident):
    payload_json = request.get_json(silent=True)
    data = PeopleService.parse_people_payload(request.files, payload_json)

    existing = PeopleService.get_by_ident(ident)
    if existing:
        PeopleService.update(ident, data)
    else:
        PeopleService.create(data)

    return ok()


@people_bp.route("/<ident>", methods=["DELETE"])
def delete_person(ident):
    PeopleService.delete(ident)
    return ok()
