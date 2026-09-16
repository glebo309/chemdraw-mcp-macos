"""Conservative graph-derived panel defaults, with explicit opt-out upstream.

Only a whole molecule present in the supplied set can become the common core.
Group names describe matched motifs, not predicted reactivity or electronic data.
"""


def _family(mol, core, match):
    owned=set(match); extra=set(range(mol.GetNumAtoms()))-owned
    if not extra:return 'reference'
    joins=[(b.GetBeginAtomIdx(),b.GetEndAtomIdx()) for b in mol.GetBonds()
           if (b.GetBeginAtomIdx() in owned)!=(b.GetEndAtomIdx() in owned)]
    if len(joins)!=1:return 'other'
    a,b=joins[0]; anchor,first=(a,b) if a in owned else (b,a)
    if not mol.GetAtomWithIdx(anchor).GetIsAromatic():return 'other'
    atoms=[mol.GetAtomWithIdx(i) for i in extra]
    nums=sorted(a.GetAtomicNum() for a in atoms)
    bonds=[b for b in mol.GetBonds() if b.GetBeginAtomIdx() in extra and b.GetEndAtomIdx() in extra]
    singles=all(b.GetBondTypeAsDouble()==1 for b in bonds)
    if len(nums)==1 and nums[0] in (9,17,35,53):return 'halogen'
    if (nums==[6,7] and any(b.GetBondTypeAsDouble()==3 for b in bonds) and
            mol.GetAtomWithIdx(first).GetAtomicNum()==6):return 'withdrawing'
    if nums==[6,9,9,9] and mol.GetAtomWithIdx(first).GetAtomicNum()==6:return 'withdrawing'
    if nums==[7,8,8] and mol.GetAtomWithIdx(first).GetAtomicNum()==7 and mol.GetAtomWithIdx(first).GetFormalCharge()==1:
        return 'withdrawing'
    if singles and all(n==6 for n in nums) and all(a.GetFormalCharge()==0 for a in atoms):return 'alkyl'
    if (singles and nums.count(8)==1 and all(n in (6,8) for n in nums) and
            mol.GetAtomWithIdx(first).GetAtomicNum()==8 and len(nums)>1 and
            all(a.GetFormalCharge()==0 for a in atoms)):return 'alkyl'
    return 'other'


def plan_drawing_defaults(records):
    from rdkit import Chem
    empty={'scaffold_smiles':None,'groups':None,'reason':'No whole supplied ring-containing parent shared by every input.'}
    if len(records)<4:return {**empty,'reason':'Fewer than four structures; no automatic scope grouping.'}
    parser=Chem.SmilesParserParams();parser.removeHs=False
    mols=[Chem.MolFromSmiles(r['canonical_smiles'],parser) for r in records]
    candidates=sorted(range(len(mols)),key=lambda i:(mols[i].GetNumAtoms(),records[i]['canonical_smiles'],i))
    parent=None
    for i in candidates:
        core=mols[i]
        if core.GetNumHeavyAtoms()<6 or not core.GetRingInfo().NumRings():continue
        if any(a.GetAtomicNum()==1 for a in core.GetAtoms()):continue
        if all(m.HasSubstructMatch(core,useChirality=True) for m in mols):parent=i;break
    if parent is None:return empty
    core=mols[parent];families={k:[] for k in ('reference','alkyl','withdrawing','halogen','other')}
    for record,mol in zip(records,mols):
        matches=mol.GetSubstructMatches(core,uniquify=False,useChirality=True,maxMatches=1000)
        if len(matches)>=1000:return {**empty,'reason':'Common-core match limit reached; provide explicit scaffold.'}
        types={_family(mol,core,m) for m in matches}
        family=next(iter(types)) if len(types)==1 else 'other'
        families[family].append(record['compound_id'])
    groups=[]
    for label,ids in (
        ('Reference / alkyl / alkoxy',families['reference']+families['alkyl']),
        ('Electron-withdrawing motifs',families['withdrawing']),
        ('Halogens',families['halogen']),('Other substitutions',families['other'])):
        if ids:groups.append({'label':label,'compound_ids':ids})
    return {'scaffold_smiles':records[parent]['canonical_smiles'],'groups':groups,
            'reason':'Exact whole supplied parent subgraph in every input, with stereochemical matching.',
            'grouping_basis':'Single aromatic attachment and exact alkyl/alkoxy, nitrile, CF3, nitro or halogen motif rules. Everything else is Other substitutions.'}
