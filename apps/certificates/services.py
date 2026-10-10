import hashlib
import hmac
import json

from django.conf import settings


def canonical_payload(certificate):
    return {"public_id": str(certificate.public_id), "serial_number": certificate.serial_number, "madrasa_id": certificate.madrasa_id, "certificate_type": certificate.certificate_type, "recipient_name": certificate.recipient_name_snapshot, "recipient_identifier": certificate.recipient_identifier_snapshot, "title": certificate.title, "body": certificate.body_snapshot, "issuer": certificate.issuer_snapshot, "credential": certificate.credential_snapshot, "issued_on": certificate.issued_on.isoformat() if certificate.issued_on else None, "revision": certificate.revision_number}


def payload_bytes(certificate):
    return json.dumps(canonical_payload(certificate), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_certificate(certificate):
    payload = payload_bytes(certificate)
    certificate.payload_hash = hashlib.sha256(payload).hexdigest()
    certificate.signature = hmac.new(settings.SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_signature(certificate):
    payload = payload_bytes(certificate)
    expected_hash = hashlib.sha256(payload).hexdigest()
    expected_signature = hmac.new(settings.SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(certificate.payload_hash, expected_hash) and hmac.compare_digest(certificate.signature, expected_signature)
