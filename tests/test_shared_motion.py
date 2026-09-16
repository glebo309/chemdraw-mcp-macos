"""Run the actual dependency-free motion controller with deterministic native mocks."""
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT=Path(__file__).parents[1]/'chemdraw_macos/shared.js'


def test_motion_reconciles_delayed_and_confirmed_noop_without_repeating_paste():
    node=shutil.which('node')
    if not node:pytest.skip('JavaScript runtime unavailable')
    checks=r'''
const assert=require('node:assert/strict');
let box=[100,100,130,140],pending=null,nudges=0;
const read=()=>box.slice();
const nudge=(axis,delta,coarse,attempt)=>{nudges++;
  // First pulse really did nothing. Second completes asynchronously.
  if(nudges===1)return;
  pending=()=>{const move=Math.sign(delta)*(coarse?10:1);box[axis]+=move;box[axis+2]+=move;};
};
const wait=()=>{if(pending){pending();pending=null;}};
let result=positionSelection({left:79,top:81},read,nudge,wait);
assert.deepEqual(box,[79,81,109,121]);
assert.equal(result.undo_steps,14); // 3 X movements + 10 Y + paste
assert.ok(result.confirmed_noops===1);
let calls=0;
assert.throws(()=>positionSelection({left:0,top:0},()=>[10,10,20,20],()=>{calls++;},()=>{}),/did not execute/);
assert.equal(calls,3);
assert.throws(()=>positionSelection({left:20,top:10},()=>[10,10,20,20],()=>{throw Error('focus lost');},()=>{}),/focus lost/);
'''
    source='global.ObjC={import:()=>{}};\n'+SCRIPT.read_text()+'\n'+checks
    result=subprocess.run([node,'-e',source],text=True,capture_output=True)
    assert result.returncode==0,result.stderr
