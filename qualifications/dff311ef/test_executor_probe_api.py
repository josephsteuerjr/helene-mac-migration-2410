"""Exact embedded caller-to-producer binding; not native platform qualification."""
import ast
import importlib.util
from pathlib import Path
import unittest

class CaptureBinding(unittest.TestCase):
    def test_embedded_capture_calls_declared_producer(self):
        root=Path(__file__).parent
        tree=ast.parse((root/'mac_executor_probe.py').read_text('utf8'))
        scripts=[n.value.value for n in ast.walk(tree) if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='capture' for t in n.targets)
                 and isinstance(n.value,ast.Constant)]
        self.assertEqual(len(scripts),1)
        calls=[n.func.attr for n in ast.walk(ast.parse(scripts[0])) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='m']
        self.assertEqual(len(calls),1)
        spec=importlib.util.spec_from_file_location('actual_capture_source',root/'capture_executor_source.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        # Invoke the exact selected API, with no package qualification implied.
        result=getattr(module,calls[0])(packages=set())
        self.assertEqual(set(result),{'platform','python_version','tools','python_packages'})
        self.assertEqual(result['python_packages'],{})

if __name__=='__main__':unittest.main()
