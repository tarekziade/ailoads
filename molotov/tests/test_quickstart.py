import os
import shutil
import tempfile

from molotov import __version__, quickstart, run
from molotov.tests.support import TestLoop, dedicatedloop, set_args


class TestQuickStart(TestLoop):
    def setUp(self):
        super().setUp()
        self._curdir = os.getcwd()
        self.tempdir = tempfile.mkdtemp()
        self.location = os.path.join(self.tempdir, "new")
        self._answers = ["", "y", self.location]

    def tearDown(self):
        os.chdir(self._curdir)
        shutil.rmtree(self.tempdir)
        super().tearDown()

    def _input(self, text):
        if self._answers == []:
            self._answers = ["", "y", self.location]
        answer = self._answers.pop()
        return answer

    def test_version(self):
        quickstart._input = self._input

        with set_args("molostart", "--version") as out:
            try:
                quickstart.main()
            except SystemExit:
                pass
        output = out[0].read().strip()
        self.assertEqual(output, __version__)

    def test_generate(self):
        quickstart._input = self._input

        with set_args("molostart"):
            quickstart.main()

        result = os.listdir(self.location)
        result.sort()
        self.assertEqual(result, ["Makefile", "loadtest.py", "molotov.json"])

        # second runs stops
        with set_args("molostart"):
            try:
                quickstart.main()
                raise AssertionError()
            except SystemExit:
                pass

    @dedicatedloop
    def test_codeworks(self):
        quickstart._input = self._input

        with set_args("molostart"):
            quickstart.main()

        result = os.listdir(self.location)
        result.sort()
        self.assertEqual(result, ["Makefile", "loadtest.py", "molotov.json"])

        os.chdir(self.location)
        with set_args("molotov", "-xv", "--max-runs", "1"):
            try:
                run.main()
            except SystemExit:
                pass
