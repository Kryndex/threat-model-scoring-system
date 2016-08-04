"""Verifies that the threat model adheres to the schema.

Todos:
    * Accept json filename as command-line arg
    * Add warnings for these conditions:
        * The same countermeasure id is listed multiple times under the same
            attack
        * An attack is missing the 'countermeasures' field or the
            'countermeasures' array under an attack is empty.
"""

import sys
import json
import warnings
import jsonschema

DEFAULT_JSON_FILENAME = 'threat model example.json'
DEFAULT_SCHEMA_FILENAME = 'threat model schema.json'

DEBUG_PRINT = False

def _main():
    filename = get_args()
    if filename is None:
        filename = DEFAULT_JSON_FILENAME

    validate_json(get_json(filename),
                  get_json(DEFAULT_SCHEMA_FILENAME))
    print "'%s' matches the specified schema." % filename

def get_args():
    """Reads command line arguments.

    Returns: json_filename to validate as str or None.
    """
    if len(sys.argv) == 1:
        return None
    elif len(sys.argv) == 2:
        return str(sys.argv[1])
    else:
        print_usage()

def get_json(filename):
    """Get JSON object from file."""
    with open(filename) as data:
        return json.load(data)

def validate_json(json_object, schema_object):
    """Raises an error if the JSON is not valid.

    Raises:
        ValidationError: Raised by `jsonschema.validate`.
    """
    jsonschema.validate(json_object, schema_object)
    check_all_countermeasure_ids_unique(json_object)
    check_all_criteria_ids_unique(json_object)
    check_all_countermeasure_ids(json_object)
    check_all_criteria_ids(json_object)
    check_all_countermeasure_descriptions(json_object)
    check_all_criteria_descriptions(json_object)
    check_all_nonce_ids_unique(json_object)
    check_unassigned_countermeasure(json_object)
    check_unassigned_criterion(json_object)

def check_all_countermeasure_ids(threat_model_json):
    """Verifies that all countermeasures listed under attacks are found.

    The id specified should match an id in the 'countermeasures' array. Also,
    if a description is provided for the countermeasure under an attack, it
    should match the same description provided in the 'countermeasures' array.

    Raises:
        ValueError if the countermeasure ID listed under an attack cannot be
        found in the 'countermeasures' array.
    """
    for attacker in threat_model_json['attackers']:
        for attack in attacker['attacks']:
            attack_name = attack['name']
            if _empty(attack, 'countermeasures'):
                continue
            for countermeasure in attack['countermeasures']:
                countermeasure_id = countermeasure['id']
                if (not is_id_in_countermeasures(threat_model_json,
                                                 countermeasure_id)):
                    raise ValueError(("The countermeasure id '%s' specified in "
                                      "attack '%s' could not be found in the "
                                      "countermeasures array.") %
                                     (countermeasure_id, attack_name))

def check_all_criteria_ids(threat_model_json):
    """Verifies that all criteria listed under countermeasures are found.

    The id specified should match an id in the 'criteria' array. Also, if a
    description is provided for the criterion under an attack, it should match
    the same description provided in the 'criteria' array.

    Raises:
        ValueError if the criterion ID listed under an attack cannot be found in
        the 'criteria' array.
    """
    for attacker in threat_model_json['attackers']:
        for attack in attacker['attacks']:
            if _empty(attack, 'countermeasures'):
                continue
            for countermeasure in attack['countermeasures']:
                countermeasure_id = countermeasure['id']
                if _empty(countermeasure, 'criteria-groups'):
                    continue
                for criteria_group in countermeasure['criteria-groups']:
                    _check_all_criteria_ids_recurse(threat_model_json,
                                                    countermeasure_id,
                                                    criteria_group)

def _check_all_criteria_ids_recurse(threat_model_json, countermeasure_id,
                                    criteria_group):
    """A criteria-group may contain criteria and/or child criteria-groups."""
    if 'criteria' in criteria_group:
        for criterion in criteria_group['criteria']:
            criterion_id = criterion['id']
            if not is_id_in_criteria(threat_model_json, criterion_id):
                raise ValueError(("The criterion id '%s' specified in "
                                  "countermeasure '%s' could not be found in "
                                  "the criteria array.") %
                                 (criterion_id, countermeasure_id))

    if 'criteria-groups' in criteria_group:
        for criteria_group_inner in criteria_group['criteria-groups']:
            _check_all_criteria_ids_recurse(threat_model_json,
                                            countermeasure_id,
                                            criteria_group_inner)

def check_all_countermeasure_descriptions(threat_model_json):
    """Verifies all countermeasure descriptions are consistent."""
    for attacker in threat_model_json['attackers']:
        for attack in attacker['attacks']:
            if _empty(attack, 'countermeasures'):
                continue
            for countermeasure in attack['countermeasures']:
                if 'description' in countermeasure:
                    _description_matches_helper(threat_model_json,
                                                'countermeasures',
                                                countermeasure['id'],
                                                countermeasure['description'])

def check_all_criteria_descriptions(threat_model_json):
    """Verifies all criteria descriptions are consistent."""
    for attacker in threat_model_json['attackers']:
        for attack in attacker['attacks']:
            if _empty(attack, 'countermeasures'):
                continue
            for countermeasure in attack['countermeasures']:
                if 'criteria-groups' in countermeasure:
                    for criteria_group in countermeasure['criteria-groups']:
                        _check_all_criteria_descriptions_recurse(
                            threat_model_json, criteria_group)

def _check_all_criteria_descriptions_recurse(threat_model_json, criteria_group):
    """A criteria-group may contain criteria and/or child criteria-groups."""
    if 'criteria' in criteria_group:
        for criterion in criteria_group['criteria']:
            if 'description' in criterion:
                _description_matches_helper(threat_model_json,
                                            'criteria',
                                            criterion['id'],
                                            criterion['description'])

    if 'criteria-groups' in criteria_group:
        for criteria_group_inner in criteria_group:
            _check_all_criteria_descriptions_recurse(threat_model_json,
                                                     criteria_group_inner)

def _description_matches_helper(threat_model_json, array_name, item_id,
                                item_description):
    for item in threat_model_json[array_name]:
        if item['id'] == item_id:
            if item['description'] != item_description:
                raise ValueError(("Descriptions are not consistent for item "
                                  "'%s': '%s' != '%s'") % (item_id,
                                                           item['description'],
                                                           item_description))

def is_id_in_countermeasures(threat_model_json, countermeasure_id):
    """Does the specified countermeasure ID appear in 'countermeasures'?

    Raises:
        ValueError if the countermeasure ID appears more than once in the
        'countermeasures' array.
    """
    found = False
    for countermeasure in threat_model_json['countermeasures']:
        if countermeasure['id'] == countermeasure_id:
            if found:
                raise ValueError(("ID '%s' appears more than once in the list "
                                  "of countermeasures.") % countermeasure_id)
            found = True
    return found

def is_id_in_criteria(threat_model_json, criterion_id):
    """Does the specified criterion ID appear in 'criteria'?

    Raises:
        ValueError if the criterion ID appears more than once in the 'criteria'
        array.
    """
    found = False
    for criteria in threat_model_json['criteria']:
        if criteria['id'] == criterion_id:
            if found:
                raise ValueError(("ID '%s' appears more than once in the list "
                                  "of criteria.") % criterion_id)
            found = True
    return found

def check_all_countermeasure_ids_unique(threat_model_json):
    """Verifies all IDs specified in 'countermeasures' are unique.

    Raises:
        ValueError if the same countermeasure ID is used multiple times for
        different countermeasures
    """
    _check_id_unique_helper(threat_model_json, 'countermeasures')

def check_all_criteria_ids_unique(threat_model_json):
    """Verifies all IDs specified in 'criteria' are unique.

    Raises:
        ValueError if the same criterion ID is used multiple times for
        different criteria
    """
    _check_id_unique_helper(threat_model_json, 'criteria')

def check_all_nonce_ids_unique(json_obj, nonce_id_set=frozenset()):
    """Verifies all nonce ids in the threat model are unique, recursively.

    Args:
        json_obj: An element within a deserialized JSON object.
        nonce_id_set (Optional[`frozenset`[str]]): Unique nonce_ids seen so far.

    Raises:
        ValueError if the same nonce-id is seen twice

    Returns:
        `frozenset`[str] of nonce_ids seen so far
    """
    if isinstance(json_obj, dict):
        if 'nonce-id' in json_obj:
            nonce_id = json_obj['nonce-id']
            dprint(nonce_id)
            if nonce_id in nonce_id_set:
                raise ValueError("The nonce-id '%s' was seen twice." % nonce_id)
            else:
                nonce_id_set = frozenset.union(nonce_id_set, [nonce_id])

        for key in json_obj:
            new_id_set = check_all_nonce_ids_unique(json_obj[key], nonce_id_set)
            nonce_id_set = frozenset.union(nonce_id_set, new_id_set)
    elif isinstance(json_obj, list):
        for elt in json_obj:
            new_id_set = check_all_nonce_ids_unique(elt, nonce_id_set)
            nonce_id_set = frozenset.union(nonce_id_set, new_id_set)

    return nonce_id_set

def check_unassigned_countermeasure(threat_model):
    """Issues warning when a countermeasure is not assigned to the threat model.

    """
    if _empty(threat_model, 'countermeasures'):
        dprint("Countermeasures is empty")
        return
    for countermeasure in threat_model['countermeasures']:
        assert 'id' in countermeasure
        counterm_id = countermeasure['id']
        dprint(counterm_id)
        found = False
        if _empty(threat_model, 'attackers'):
            continue
        for attacker in threat_model['attackers']:
            if _empty(attacker, 'attacks'):
                continue
            for attack in attacker['attacks']:
                if _empty(attack, 'countermeasures'):
                    continue
                for counterm in attack['countermeasures']:
                    if counterm['id'] == counterm_id:
                        found = True
                        dprint("Found countermeasure %s in an attack" %
                               counterm_id)
                        break
        if not found:
            dprint(threat_model['name'])
            warnings.warn(("The countermeasure '%s' could not be found under "
                           "any attack in the threat model.") % counterm_id)

def check_unassigned_criterion(threat_model):
    """Issues warning when a criterion is not assigned to the threat model."""
    if _empty(threat_model, 'criteria'):
        dprint("Criteria array is empty")
        return
    for criterion in threat_model['criteria']:
        assert 'id' in criterion
        criterion_id = criterion['id']
        dprint("Looking for criterion '%s'" % criterion_id)
        found = False
        if _empty(threat_model, 'attackers'):
            continue
        for attacker in threat_model['attackers']:
            if _empty(attacker, 'attacks'):
                continue
            for attack in attacker['attacks']:
                if _empty(attack, 'countermeasures'):
                    continue
                for countermeasure in attack['countermeasures']:
                    if _is_criterion_in_countermeasure(countermeasure,
                                                       criterion_id):
                        found = True
                        dprint("Found criterion '%s'" % criterion_id)
                        break
        if not found:
            dprint(threat_model['name'])
            warnings.warn(("The criterion '%s' could not be found under any "
                           "countermeasure in the threat model.") %
                          criterion_id)

def _is_criterion_in_countermeasure(countermeasure, criterion_id):
    """Returns whether criterion ID is found in specified countermeasure obj.

    Returns: bool: whether criterion ID was found
    """
    if _empty(countermeasure, 'criteria-groups'):
        return False
    for criteria_group in countermeasure['criteria-groups']:
        if _is_criterion_in_countermeasure_recurse(criteria_group,
                                                   criterion_id):
            return True
    return False

def _is_criterion_in_countermeasure_recurse(criteria_group, criterion_id):
    """A criteria group may continue criteria or child  criteria groups."""
    if 'criteria' in criteria_group:
        for criterion in criteria_group['criteria']:
            if 'id' in criterion and criterion['id'] == criterion_id:
                return True

    if 'criteria-groups' in criteria_group:
        for criteria_group_inner in criteria_group:
            if _is_criterion_in_countermeasure_recurse(criteria_group_inner,
                                                       criterion_id):
                return True

    return False

def _check_id_unique_helper(threat_model_json, array_name):
    ids = []
    for item in threat_model_json[array_name]:
        if item['id'] in ids:
            raise ValueError("The ID '%s' is used multiple times." % item['id'])
        ids.append(item['id'])

def _empty(dict_parent, array_child_name):
    return (array_child_name not in dict_parent or
            len(dict_parent[array_child_name]) == 0)

def dprint(data):
    """Print debug data, if enabled."""
    if DEBUG_PRINT:
        print "DEBUG: %s" % str(data)

def print_usage():
    """Prints syntax for usage and exits the program."""
    print(("Usage:\n"
           "\tpython validate_json.py [threat-model-file.json]"))
    sys.exit()

if __name__ == '__main__':
    _main()
