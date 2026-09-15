"""Published example must point to the actual donating electron source."""
import json
from pathlib import Path

def test_sn2_recipe_uses_negative_charge_and_bond_source():
    recipe=json.loads((Path(__file__).parents[1]/'examples/sn2-annotation-recipe.json').read_text())
    assert recipe['arrows'][0]['source']=={'kind':'symbol','id':'1500'}
    assert recipe['arrows'][1]['source']=={'kind':'bond','id':'2105','offset':[0,0]}
