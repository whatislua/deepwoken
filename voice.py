"""Voice replies for party messages: listens on the mic you choose for a short list of phrases
("yes", "no", "on my way"...) and sends what you said as a party message.

It only listens for a few seconds after a friend's message arrives, or while you hold the voice key,
so it isn't transcribing you the rest of the time. Uses Windows' own offline speech recognizer (SAPI),
and nothing but the recognised phrase leaves your PC.
"""
import threading
import time

PHRASES = ["yes", "no", "on my way", "need help", "wait", "coming", "okay", "thanks", "run", "low hp"]

SRA_TOP_LEVEL, SRA_DYNAMIC = 1, 32
SGDS_INACTIVE, SGDS_ACTIVE = 0, 1


def list_mics():
    """Names of the microphones Windows' speech recognizer can use."""
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        ins = win32com.client.Dispatch("SAPI.SpInprocRecognizer").GetAudioInputs()
        return [ins.Item(i).GetDescription() for i in range(ins.Count)]
    except Exception:
        return []


class VoiceReplies:
    def __init__(self, log, on_phrase):
        self.log = log
        self.on_phrase = on_phrase   # called with the recognised phrase
        self.settings = None
        self.listen_until = 0.0
        self.held = False
        self.status = "off"
        self._thread = None
        self._stop = threading.Event()

    # -- control (any thread)
    def configure(self, cfg):
        settings = (bool(cfg.get("enabled")), cfg.get("mic", ""), tuple(cfg.get("phrases") or PHRASES))
        if settings == self.settings:
            return
        self.settings = settings
        self.stop()
        if settings[0]:
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(settings, self._stop), daemon=True)
            self._thread.start()
        else:
            self.status = "off"

    def stop(self):
        self._stop.set()

    def listen_for(self, seconds):
        self.listen_until = max(self.listen_until, time.time() + seconds)

    def listening(self):
        return self.held or time.time() < self.listen_until

    # -- recognizer thread
    def _run(self, settings, stop):
        _, mic, phrases = settings
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            rec = win32com.client.Dispatch("SAPI.SpInprocRecognizer")
            ins = rec.GetAudioInputs()
            tokens = [ins.Item(i) for i in range(ins.Count)]
            chosen = next((t for t in tokens if t.GetDescription() == mic), tokens[0] if tokens else None)
            if chosen is None:
                self.status = "no microphone found"
                return
            rec.AudioInput = chosen
            owner = self

            class Events:
                def OnRecognition(self, stream, position, kind, result):
                    owner._heard(win32com.client.Dispatch(result))

            ctx = win32com.client.DispatchWithEvents(rec.CreateRecoContext(), Events)
            grammar = ctx.CreateGrammar()
            rule = grammar.Rules.Add("replies", SRA_TOP_LEVEL | SRA_DYNAMIC, 0)
            for p in phrases:
                rule.InitialState.AddWordTransition(None, p)
            grammar.Rules.Commit()
            self.status = f"ready ({chosen.GetDescription()})"
            active = None
            while not stop.is_set():
                want = self.listening()
                if want != active:
                    grammar.CmdSetRuleState("replies", SGDS_ACTIVE if want else SGDS_INACTIVE)
                    active = want
                pythoncom.PumpWaitingMessages()
                time.sleep(0.02)
            grammar.CmdSetRuleState("replies", SGDS_INACTIVE)
        except Exception as e:
            self.status = f"voice error: {e}"
            self.log(f"voice: {e}")

    def _heard(self, result):
        if not self.listening():
            return
        try:
            info = result.PhraseInfo
            text = info.GetText()
            confidence = info.Rule.Confidence   # -1 low, 0 normal, 1 high
        except Exception:
            return
        if text and confidence >= 0:
            self.listen_until = 0.0  # one reply per message
            self.on_phrase(text)
