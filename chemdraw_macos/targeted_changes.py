"""Explicit local graph changes used by the snapshot-targeted editor."""
import copy
import math
import statistics
import xml.etree.ElementTree as ET

from .editing import ELEMENTS, _label, _decoded, _tetra
from .polish import numbers, bond_lengths


def _hydrogens(value):
    if type(value) is not int or not 0<=value<=4:raise ValueError('Explicit hydrogens must be an integer from 0 to 4')
    return value


def label(root,node):
    _label(root,node)
    charge=int(node.get('Charge','0'))
    if charge:
        t=node.find('t')
        if t is None:
            t=ET.SubElement(node,'t',{'p':node.get('p')})
            ET.SubElement(t,'s',{'font':root.get('LabelFont','3'),'size':root.get('LabelSize','10'),'face':'96'}).text='C'+('H' if int(node.get('NumHydrogens','0')) else '')+(node.get('NumHydrogens') if int(node.get('NumHydrogens','0'))>1 else '')
        ET.SubElement(t,'s',{'font':root.get('LabelFont','3'),'size':root.get('LabelSize','10'),'face':'64'}).text=('+' if charge>0 else '-')


def apply_change(root,f,obj,selected,op,before,mapping,report):
    from .targeted import _root, _isolated, _fresh_ids
    kind=op['kind'];nodes={n.get('id'):n for n in f.findall('n')}
    if kind=='set_atom':
        if selected['kind']!='atom' or set(op)!={'kind','element','hydrogens','charge'}:raise ValueError('set_atom needs an atom, element, hydrogens and charge')
        symbol=op['element'];h=_hydrogens(op['hydrogens']);charge=op['charge']
        if symbol not in ELEMENTS or type(charge) is not int or charge not in (-1,0,1):raise ValueError('Supported elements and charge -1, 0 or +1 required')
        if obj['isotope'] or obj['stereo']!='CHI_UNSPECIFIED':raise ValueError('Cannot change an isotope-labelled atom or assigned stereocentre')
        n=nodes[obj['id']];n.set('Element',str(ELEMENTS[symbol]));n.set('NumHydrogens',str(h));n.set('Charge',str(charge));label(root,n)
        report['requested_atoms']={obj['id']:{'element':symbol,'hydrogens':h,'charge':charge}}
    elif kind=='set_bond_order':
        if selected['kind']!='bond' or set(op)!={'kind','order','hydrogens'}:raise ValueError('set_bond_order needs one bond, order and endpoint hydrogens')
        b=f.find(f"b[@id='{obj['id']}']");order=op['order'];hs=op['hydrogens']
        if type(order) is not int or order not in (1,2,3):raise ValueError('Bond order must be 1, 2 or 3')
        parsed=before.GetBondBetweenAtoms(mapping[obj['begin']],mapping[obj['end']])
        if parsed.GetIsAromatic() or str(parsed.GetStereo())!='STEREONONE' or b.get('Display','Solid')!='Solid' or b.get('Display2','Solid')!='Solid':raise ValueError('Cannot change aromatic, stereo or special-display bond order')
        if not isinstance(hs,dict) or set(hs)!={obj['begin'],obj['end']}:raise ValueError('Both endpoint hydrogen counts must be explicit')
        b.set('Order',str(order));b.attrib.pop('BS',None)
        for aid,h in hs.items():nodes[aid].set('NumHydrogens',str(_hydrogens(h)));label(root,nodes[aid])
        report['requested_hydrogens']=hs
    elif kind=='remove_substituent':
        if selected['kind']!='bond' or set(op)!={'kind','keep_atom_id','hydrogens'}:raise ValueError('Removal needs one bond, keep_atom_id and remaining hydrogens')
        keep=op['keep_atom_id'];h=_hydrogens(op['hydrogens'])
        if keep not in (obj['begin'],obj['end']):raise ValueError('Kept atom must be a cut bond endpoint')
        if obj['order']!='1' or obj['display']!='Solid':raise ValueError('Removal requires a plain single connecting bond')
        start=obj['end'] if keep==obj['begin'] else obj['begin'];adj={i:set() for i in nodes}
        for b in f.findall('b'):
            if b.get('id')==obj['id']:continue
            adj[b.get('B')].add(b.get('E'));adj[b.get('E')].add(b.get('B'))
        removed=set();todo=[start]
        while todo:
            i=todo.pop()
            if i in removed:continue
            removed.add(i);todo.extend(adj[i]-removed)
        if keep in removed:raise ValueError('Cut does not disconnect a substituent; ring bonds cannot be removed')
        if len(nodes)-len(removed)<2:raise ValueError('Keep at least two atoms in the retained molecule')
        removed_bonds={b.get('id') for b in f.findall('b') if b.get('B') in removed or b.get('E') in removed}
        for b in f.findall('b'):
            if b.get('id') not in removed_bonds and set(b.get('CrossingBonds','').split())&removed_bonds:raise ValueError('Removal would leave a crossing reference dangling')
        for e in list(f):
            if e.get('id') in removed|removed_bonds:f.remove(e)
        nodes[keep].set('NumHydrogens',str(h));label(root,nodes[keep])
        report.update(removed_atom_ids=sorted(removed),removed_bond_ids=sorted(removed_bonds),requested_hydrogens={keep:h})
    elif kind=='attach_fragment':
        if selected['kind']!='atom' or set(op)!={'kind','fragment_cdxml','attachment_atom_id','angle_degrees'}:raise ValueError('Fragment needs supplied CDXML, its attachment atom and angle_degrees')
        other=_root(op['fragment_cdxml']);fragments=other.findall('page/fragment')
        if len(fragments)!=1 or len(other.find('page'))!=1:raise ValueError('Supply one fragment without captions')
        g=fragments[0];mol,amap=_decoded(ET.tostring(other,encoding='unicode'));anchor=op['attachment_atom_id']
        if anchor not in amap:raise ValueError('Fragment attachment atom absent')
        if not 1<=len(amap)<=100:raise ValueError('Attachment fragment needs 1 to 100 atoms')
        target=before.GetAtomWithIdx(mapping[obj['id']]);donor=mol.GetAtomWithIdx(amap[anchor])
        for a in (target,donor):
            if a.GetSymbol() not in ('C','N','O','S') or a.GetFormalCharge() or a.GetIsotope() or a.GetTotalNumHs()<1 or str(a.GetChiralTag())!='CHI_UNSPECIFIED' or any(n.GetAtomicNum()==1 for n in a.GetNeighbors()):raise ValueError('Attachment endpoints must be neutral nonisotopic H-bearing C/N/O/S without assigned stereo or explicit H atoms')
        angle=op['angle_degrees']
        if type(angle) not in (int,float) or not math.isfinite(angle) or not -360<=angle<=360:raise ValueError('Finite explicit fragment angle required')
        size=statistics.median(bond_lengths(f));scale=size/statistics.median(bond_lengths(g) or [size]);origin=numbers(g.find(f"n[@id='{anchor}']").get('p'),2)
        pts=[numbers(n.get('p'),2) for n in g.findall('n') if n.get('id')!=anchor]
        vx=sum(p[0]-origin[0] for p in pts);vy=sum(p[1]-origin[1] for p in pts)
        if not pts:vx,vy=1.,0.
        elif math.hypot(vx,vy)<.001:raise ValueError('Ambiguous fragment outward axis; supply a terminal attachment atom')
        theta=math.radians(angle)
        # A terminal atom becomes an internal vertex. A 180-degree join hides
        # skeletal carbon; preserve supplied internal geometry with a rigid turn.
        outward=theta+(math.pi/3 if donor.GetDegree()==1 else 0)
        rotation=outward-math.atan2(vy,vx);c,s=math.cos(rotation),math.sin(rotation)
        px,py=obj['position_pt'];px+=size*math.cos(theta);py+=size*math.sin(theta)
        ids=_fresh_ids(root,len(list(g))+1);renamed={e.get('id'):nid for e,nid in zip(g,ids)}
        for n in g.findall('n'):
            x,y=numbers(n.get('p'),2);x=(x-origin[0])*scale;y=(y-origin[1])*scale
            n.set('p',f'{px+c*x-s*y:.6f} {py+s*x+c*y:.6f}')
            n.set('NumHydrogens',str(mol.GetAtomWithIdx(amap[n.get('id')]).GetTotalNumHs()-(n.get('id')==anchor)))
            # Regenerate labels using destination typography, not source font IDs.
            if n.get('Isotope'):raise ValueError('Isotope labels in attachment fragments are not supported')
            for t in n.findall('t'):n.remove(t)
            for key in ('LabelFont','LabelSize','LabelFace'):n.attrib.pop(key,None)
            label(root,n)
        for e in g:
            oldid=e.get('id');e.set('id',renamed[oldid])
            if e.tag=='b':
                for key in ('B','E'):e.set(key,renamed[e.get(key)])
                if e.get('CrossingBonds'):e.set('CrossingBonds',' '.join(renamed[i] for i in e.get('CrossingBonds').split()))
                e.set('LineWidth',root.get('LineWidth','1.58'));e.set('BoldWidth',root.get('BoldWidth','2'))
            f.append(copy.deepcopy(e))
        ET.SubElement(f,'b',{'id':ids[-1],'B':obj['id'],'E':renamed[anchor],'Order':'1','LineWidth':root.get('LineWidth','1.58'),'BoldWidth':root.get('BoldWidth','2')})
        nodes[obj['id']].set('NumHydrogens',str(target.GetTotalNumHs()-1));label(root,nodes[obj['id']])
        report.update(added_atoms=len(amap),added_bonds=len(g.findall('b'))+1,
                      fragment_atom_id_map={i:renamed[i] for i in amap},fragment_stereo=_tetra(mol,{renamed[i]:v for i,v in amap.items()}))
    else:raise ValueError('Unknown targeted change')
