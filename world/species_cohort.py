"""Cohort-scoped species vocabularies for generated encounters."""
from functools import lru_cache
import json
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = APP_ROOT / 'engines/expansion-native'
CATALOGUE_PATH = Path(__file__).resolve().with_name('expansion_species.json')
LEGACY_COHORT = 'vanilla'
EXPANSION_COHORT = 'expansion-native'


@lru_cache(maxsize=2)
def catalogue(cohort=LEGACY_COHORT):
    if cohort == LEGACY_COHORT:
        from .cave_species import SPECIES
        return SPECIES
    if cohort != EXPANSION_COHORT:
        raise ValueError('unsupported species cohort')
    try:
        payload = json.loads(CATALOGUE_PATH.read_text())
        if payload.get('cohort') != EXPANSION_COHORT or payload.get('catalogue_source') != 'compiler-preprocessed enabled gSpeciesInfo family definitions':
            raise ValueError
        result = payload['species']
        if not isinstance(result, dict) or not result or any(type(k) is not str or type(v) is not int for k, v in result.items()):
            raise ValueError
        return result
    except (OSError, KeyError, TypeError, json.JSONDecodeError, ValueError):
        raise ValueError('Expansion species catalogue is unavailable; build/export the selected engine catalogue first') from None


def species_id(name, cohort=LEGACY_COHORT):
    if type(name) is not str:
        raise ValueError('invalid wildlife species or level')
    try:
        return catalogue(cohort)[name]
    except KeyError:
        raise ValueError('invalid wildlife species or level') from None


def contains_species_id(value, cohort=LEGACY_COHORT):
    return type(value) is int and value in catalogue(cohort).values()
