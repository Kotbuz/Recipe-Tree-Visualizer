def items_match(required_name: str, candidate_name: str) -> bool:
    if not required_name or not candidate_name:
        return False

    required = required_name.lower()
    candidate = candidate_name.lower()

    if required == candidate:
        return True
    if candidate.endswith(f" {required}"):
        return True
    return required.endswith(f" {candidate}")
