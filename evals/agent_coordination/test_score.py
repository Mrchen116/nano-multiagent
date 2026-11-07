"""Uncertain sends retain auditable evidence without being reported as delivered."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from score import evidence


class ScoreTest(unittest.TestCase):
    def test_unknown_send_has_no_attributed_handoff_receipt(self):
        root=[{'type':'subagent/catalog','data':{'childId':'child'}}]
        child=[{'seq':14,'time':2000,'type':'user/message','data':{'source':{'kind':'user'},'content':[{'type':'text','text':'hello'}]}}]
        wire=[{'id':'child','type':'child_request','at':3000,'messages':[{'role':'user','content':'hello'}]}]
        case={'id':'example','nodes':[{'id':'U','type':'user_message'}]}
        observation={'root':'root','nodes':{'U':{'status':'uncertain','text':'hello'}}}
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp);(run/'example-B.json').write_text(json.dumps(observation))
            with patch('score.native_events',side_effect=lambda run,session:root if session=='root' else child),patch('score.read_wire',return_value=wire):
                result=evidence(run,'B',case,{})
        self.assertEqual(result['handoffs']['U']['status'],'uncertain')
        self.assertEqual(result['handoffs']['U']['actual_text'],'hello')
        self.assertEqual(result['handoffs']['U']['receipts'],[])
        self.assertEqual(result['handoffs']['U']['queued'],[])


if __name__=='__main__':unittest.main()
