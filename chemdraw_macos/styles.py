"""Bounded style extraction, not a general CDX chemistry converter.

Binary field definitions follow the manufacturer's CDX SDK archived by IUPAC.
Only document-level numerical typography settings are applied; all other
properties are reported, not silently claimed as imported.
"""
import hashlib
import math
from pathlib import Path
import struct
import json
import subprocess
import sys

REQUIRED={'BondLength','LineWidth','BoldWidth','LabelSize','CaptionSize','font'}
DEFAULTS={'BondSpacing':'18','ChainAngle':'120','MarginWidth':'1.6','HashSpacing':'2.5'}
LIMITS={'BondLength':(5,100),'LineWidth':(.1,5),'BoldWidth':(.1,10),
        'LabelSize':(4,72),'CaptionSize':(4,72),'BondSpacing':(1,100),
        'ChainAngle':(0,180),'MarginWidth':(0,10),'HashSpacing':(.1,10)}
FACES={0,1,2,3,96,97,98,99}

def _installed_fonts():
    if sys.platform!='darwin':raise ValueError('Custom font availability requires the rendering Mac')
    script='ObjC.import("AppKit"); JSON.stringify(ObjC.deepUnwrap($.NSFontManager.sharedFontManager.availableFontFamilies));'
    try:
        r=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',script],capture_output=True,text=True,check=True,timeout=10)
        names=json.loads(r.stdout)
        if not isinstance(names,list) or not all(isinstance(s,str) for s in names):raise ValueError('Invalid font inventory')
        return names
    except (subprocess.SubprocessError,json.JSONDecodeError) as exc:raise ValueError('Cannot verify installed font families') from exc

def require_style_fonts(preset):
    if not isinstance(preset,dict):return
    spec=validate_style(preset);fonts=set(_installed_fonts())
    missing={spec['font'],spec.get('CaptionFontName',spec['font'])}-fonts
    if missing:raise ValueError('Missing custom font families: '+', '.join(sorted(missing)))

def validate_style(spec):
    if not isinstance(spec,dict) or not REQUIRED<=set(spec) or set(spec)-REQUIRED-set(DEFAULTS)-{'CaptionFontName','LabelFace','CaptionFace'}:
        raise ValueError('Custom style requires numerical bond/font settings and only supported fields')
    result={}
    for key,value in spec.items():
        if key in ('font','CaptionFontName'):
            if not isinstance(value,str) or not value.strip() or len(value)>120 or any(ord(c)<32 or ord(c)==127 for c in value):
                raise ValueError('Invalid font family name')
            result[key]=value
        elif key in ('LabelFace','CaptionFace'):
            if isinstance(value,bool) or str(value) not in {str(i) for i in FACES}:raise ValueError('Unsupported font face')
            result[key]=str(value)
        else:
            try:v=float(value)
            except (ValueError,TypeError) as exc:raise ValueError('Invalid numerical style setting') from exc
            if isinstance(value,bool) or not math.isfinite(v) or not LIMITS[key][0]<=v<=LIMITS[key][1]:raise ValueError('Style setting outside supported limits: '+key)
            result[key]=format(v,'.10g')
    return {**DEFAULTS,**result}

def _binary_properties(data):
    header=b'VjCD0100'+b'\x04\x03\x02\x01'
    if data[:12]!=header:raise ValueError('Invalid CDX header')
    # The archived SDK describes 28 bytes; native ChemDraw 23 writes 22.
    # Accept these two explicit layouts only, never scan arbitrary offsets.
    if data[12:22]==bytes(10) and data[22:24]==b'\x00\x80':pos=22
    elif data[12:28]==bytes(16) and data[28:30]==b'\x00\x80':pos=28
    else:raise ValueError('Invalid CDX header/document boundary')
    count=0
    def take(n):
        nonlocal pos
        if n<0 or pos+n>len(data):raise ValueError('Truncated CDX property')
        out=data[pos:pos+n];pos+=n;return out
    def integer(n):return int.from_bytes(take(n),'little')
    if integer(2)!=0x8000:raise ValueError('Expected CDX document')
    take(4);props={};depth=1
    while depth:
        count+=1
        if count>100000 or depth>64:raise ValueError('CDX complexity limit exceeded')
        tag=integer(2)
        if tag==0:depth-=1;continue
        if tag&0x8000:take(4);depth+=1;continue
        length=integer(2)
        if length==65535:length=integer(4)
        payload=take(length)
        if depth==1:
            if tag in props:raise ValueError('Duplicate document property')
            props[tag]=payload
    if data[pos:] not in (b'',b'\0\0'):raise ValueError('Unexpected trailing CDX data')
    return props

def _fonts(data):
    if len(data)<4:raise ValueError('Truncated CDX font table')
    platform,count=struct.unpack_from('<HH',data);pos=4;fonts={}
    if platform not in (0,1) or count>1000:raise ValueError('Unsupported font table')
    for _ in range(count):
        if pos+6>len(data):raise ValueError('Truncated font entry')
        fid,charset,length=struct.unpack_from('<HHH',data,pos);pos+=6
        if pos+length>len(data) or fid in fonts:raise ValueError('Invalid font entry')
        try:fonts[fid]=data[pos:pos+length].decode('ascii')
        except UnicodeError as exc:raise ValueError('Non-ASCII binary font names require native inspection') from exc
        pos+=length
    if pos!=len(data):raise ValueError('Trailing font table data')
    return fonts

def _decode_binary(data):
    props=_binary_properties(data);used=set();spec={}
    def read(tag,size,signed=False):
        v=props[tag]
        if len(v)!=size:raise ValueError('Invalid size for style property '+hex(tag))
        used.add(tag);return int.from_bytes(v,'little',signed=signed)
    for tag,key in {0x803:'ChainAngle',0x805:'BondLength',0x806:'BoldWidth',0x807:'LineWidth',0x808:'MarginWidth',0x809:'HashSpacing'}.items():
        if tag in props:spec[key]=str(read(tag,4,True)/65536)
    if 0x804 in props:spec['BondSpacing']=str(read(0x804,2)/10)
    fonts=_fonts(props.get(0x100,b''));used.add(0x100)
    for tag,prefix,fontkey in [(0x80a,'Label','font'),(0x80b,'Caption','CaptionFontName')]:
        values={}
        if tag in props:
            if len(props[tag])!=8:raise ValueError('Invalid font style length')
            fid,face,size,color=struct.unpack('<HHHH',props[tag]);used.add(tag)
            values={'Font':fid,'Face':face,'Size':size}
            if color:used.discard(tag)
        base=0x81a if prefix=='Label' else 0x81b
        for delta,key in [(0,'Font'),(2,'Size'),(4,'Face')]:
            if base+delta in props:values[key]=read(base+delta,2)
        if 'Font' in values:
            if values['Font'] not in fonts:raise ValueError('Unknown referenced font')
            spec[fontkey]=fonts[values['Font']]
        if 'Size' in values:spec[prefix+'Size']=str(values['Size']/20)
        if 'Face' in values:spec[prefix+'Face']=str(values['Face'])
    return spec,[f'0x{k:04x}' for k in sorted(set(props)-used)]

def inspect_style_file(path):
    source=Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or source.stat().st_size>10_000_000:raise ValueError('Style source must be a file of at most 10 MB')
    data=source.read_bytes()
    if source.suffix.lower() in ('.cds','.cdx'):
        spec,unapplied=_decode_binary(data);kind='CDX document style'
    elif source.suffix.lower()=='.cdxml':
        from .core import validate_cdxml
        root=validate_cdxml(data.decode('utf-8'));spec={k:root.get(k) for k in LIMITS if root.get(k) is not None}
        tables=root.findall('fonttable')
        if len(tables)!=1:raise ValueError('Style requires exactly one font table')
        fonts={}
        for entry in tables[0].findall('font'):
            fid=entry.get('id')
            if fid is None or fid in fonts:raise ValueError('Missing or duplicate font ID')
            fonts[fid]=entry.get('name')
        for attr,key in [('LabelFont','font'),('CaptionFont','CaptionFontName')]:
            if root.get(attr) not in fonts:raise ValueError('Style requires explicit resolved label and caption fonts')
            spec[key]=fonts[root.get(attr)]
        for key in ('LabelFace','CaptionFace'):
            if root.get(key) is not None:spec[key]=root.get(key)
        unapplied=sorted(set(root.attrib)-set(LIMITS)-{'LabelFont','CaptionFont','LabelFace','CaptionFace'})
        kind='CDXML document style'
    else:raise ValueError('Supported style inputs: .cds, .cdx, .cdxml')
    defaults=sorted(set(DEFAULTS)-set(spec))
    if 'CaptionFontName' not in spec:defaults.append('CaptionFontName')
    preset=validate_style(spec)
    if source.read_bytes()!=data:raise ValueError('Style source changed during inspection')
    return {'schema_version':1,'source':str(source),'sha256':hashlib.sha256(data).hexdigest(),
            'format':kind,'preset':preset,'defaults_used':defaults,'unapplied_properties':unapplied,
            'font_availability':'not_checked','network_used':False,
            'limitations':'Document style subset only. No chemistry, page layout, colour palette, proprietary template content or fonts copied. Font availability must be checked on the rendering Mac.'}


def verify_custom_style(expected, native, preset):
    """Check native saved custom settings, independently of graph/layout checks.

    Builtin and custom presets use the same verification. Font IDs may change.
    Text runs may split. Caption profiles preserve
    intentional sizes, for example a reaction's larger plus signs. Chemical
    superscript/subscript bits are not overwritten or certified by this check.
    """
    from .core import validate_cdxml, preset_settings
    spec=validate_style(preset_settings(preset));old=validate_cdxml(expected);new=validate_cdxml(native)
    # ChemDraw stores font sizes in twentieths of a point, and native XML
    # measurements commonly use two decimals. Report these tolerances honestly.
    tolerances={key:(.050001 if key in ('LabelSize','CaptionSize') else .010001) for key in LIMITS}
    def numerical(value,target,key):
        try:actual=float(value)
        except (TypeError,ValueError) as exc:raise ValueError('Native custom style missing '+key) from exc
        if not math.isfinite(actual) or abs(actual-float(target))>tolerances[key]:
            raise ValueError('Native custom style changed '+key)
    def font_table(root):
        tables=root.findall('fonttable')
        if len(tables)!=1:raise ValueError('Native custom style requires one font table')
        result={}
        for item in tables[0].findall('font'):
            if item.get('id') is None or item.get('id') in result or not item.get('name'):
                raise ValueError('Native custom style has ambiguous font IDs')
            result[item.get('id')]=item.get('name')
        return result
    oldfonts=font_table(old);fonts=font_table(new)
    wanted_fonts={'LabelFont':spec['font'],'CaptionFont':spec.get('CaptionFontName',spec['font'])}
    for key,target in wanted_fonts.items():
        if fonts.get(new.get(key))!=target:raise ValueError('Native custom style changed '+key+' font family')
    for key,target in spec.items():
        if key in LIMITS:numerical(new.get(key),target,key)
        elif key in ('LabelFace','CaptionFace'):
            default='0' if key=='CaptionFace' else '96'
            if int(new.get(key,default))&3 != int(target)&3:raise ValueError('Native custom style changed '+key)
    parents={child:parent for parent in new.iter() for child in parent}
    def inherited(element,key,default=None):
        while element is not None:
            if element.get(key) is not None:return element.get(key)
            element=parents.get(element)
        return default
    # Explicit fragment/node/bond/text settings override the document. Check
    # every supported override rather than validating only the root defaults.
    for element in new.iter():
        if element is new:continue
        for key,target in spec.items():
            if key in LIMITS and key in element.attrib:numerical(element.get(key),target,key)
            elif key in ('LabelFace','CaptionFace') and key in element.attrib:
                if int(element.get(key))&3 != int(target)&3:raise ValueError('Native custom style changed local '+key)
        for key,target in wanted_fonts.items():
            if key in element.attrib and fonts.get(element.get(key))!=target:
                raise ValueError('Native custom style changed local '+key+' font family')
    for node in new.iter('n'):
        for run in node.iter('s'):
            font=run.get('font',inherited(node,'LabelFont'))
            if fonts.get(font)!=spec['font']:raise ValueError('Native custom style changed atom font family')
            numerical(run.get('size',inherited(node,'LabelSize')),spec['LabelSize'],'LabelSize')
            if 'LabelFace' in spec and int(run.get('face',inherited(node,'LabelFace','96')))&3 != int(spec['LabelFace'])&3:
                raise ValueError('Native custom style changed atom face')
    def caption_profiles(root,table):
        profiles={}
        atomtexts={id(text) for node in root.iter('n') for text in node.iter('t')}
        for text in root.iter('t'):
            if id(text) in atomtexts:continue
            chars=[]
            for run in text.iter('s'):
                name=table.get(run.get('font',root.get('CaptionFont')))
                if name is None:raise ValueError('Native custom style has unresolved caption font')
                try:
                    size=float(run.get('size',root.get('CaptionSize')))
                    face=int(run.get('face',root.get('CaptionFace','0')))&3
                except (TypeError,ValueError) as exc:raise ValueError('Native custom style has invalid caption typography') from exc
                if not math.isfinite(size):raise ValueError('Native custom style has invalid caption size')
                chars.extend((char,name,size,face) for char in (run.text or ''))
            key=''.join(item[0] for item in chars)
            profiles.setdefault(key,[]).append(chars)
        return {key:sorted(value) for key,value in profiles.items()}
    expected_profiles=caption_profiles(old,oldfonts);actual_profiles=caption_profiles(new,fonts)
    if expected_profiles.keys()!=actual_profiles.keys():raise ValueError('Native custom style caption text changed')
    for text,profiles in expected_profiles.items():
        actual=actual_profiles[text]
        if len(profiles)!=len(actual):raise ValueError('Native custom style caption count changed')
        for planned,observed in zip(profiles,actual):
            if len(planned)!=len(observed):raise ValueError('Native custom style caption text changed')
            for left,right in zip(planned,observed):
                if (left[0],left[1],left[3])!=(right[0],right[1],right[3]):
                    raise ValueError('Native custom style changed caption font or face')
                numerical(right[2],left[2],'CaptionSize')
    return {'verified':True,'scope':'supported numerical settings, font families, sizes and bold/italic faces',
            'numerical_tolerances':tolerances,'chemical_script_bits':'not independently verified',
            'glyphs_and_font_rendering':'visual review required'}
