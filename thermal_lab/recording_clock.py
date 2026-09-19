"""Recording duration uses the acquisition start, independently of camera uptime."""
import time


def duration_text(seconds):
    seconds=max(0,int(seconds));hours,seconds=divmod(seconds,3600);minutes,seconds=divmod(seconds,60)
    return f'{hours:02}:{minutes:02}:{seconds:02}'


class RecordingClock:
    def __init__(self):self.origin=None;self.elapsed=0.;self.label='Recording'
    def start(self,origin):self.origin=origin;self.elapsed=0.;self.label='Recording'
    def finish(self,elapsed,complete=True):
        self.elapsed=max(0,elapsed);self.origin=None;self.label='Recorded' if complete else 'Interrupted'
    def interrupt(self):
        if self.origin is not None:self.finish(time.monotonic()-self.origin,False)
    def text(self):
        return self.label+'  '+duration_text(time.monotonic()-self.origin if self.origin is not None else self.elapsed)
