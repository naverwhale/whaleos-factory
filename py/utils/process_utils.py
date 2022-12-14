# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import getpass
from io import StringIO
import logging
import os
import pipes
import re
import select
import signal
import subprocess
import sys
import threading
import time
import traceback

# Use subprocess.CalledProcessError for invocation exceptions.
class CalledProcessError(subprocess.CalledProcessError):
  """A CalledProcessError with a workaround repr."""

  def __repr__(self):
    msg = 'CalledProcessError(returncode=%d, cmd=%r, stdout=%r, stderr=%r)'
    return msg % (self.returncode, self.cmd, self.stdout, self.stderr)


try:
  PIPE = subprocess.PIPE
  STDOUT = subprocess.STDOUT
  DEVNULL = subprocess.DEVNULL
  Popen = subprocess.Popen
  TimeoutExpired = subprocess.TimeoutExpired
except Exception:
  # Hack for HWID Service on AppEngine. The subprocess module on AppEngine
  # doesn't contain these attributes. HWID Service will not use all of these
  # attributes. This makes AppEngine won't complain we are using process_utils.
  PIPE = None
  STDOUT = None
  DEVNULL = None
  Popen = object
  TimeoutExpired = None


def GetLines(data, strip=False):
  """Returns a list of all lines in data.

  Args:
    strip: If True, each line is stripped.
  """
  ret = StringIO(data).readlines()
  if strip:
    ret = [x.strip() for x in ret]
  return ret


def IsProcessAlive(pid, ppid=None):
  """Returns true if the named process is alive and not a zombie.

  A PPID (parent PID) can be provided to be more specific to which process you
  are watching.  If there is a process with the same PID running but the PPID is
  not the same, then this is unlikely to be the same process, but a newly
  started one.  The function will return False in this case.

  Args:
    pid: process PID for checking
    ppid: specified the PID of the parent of given process.  If the PPID does
      not match, we assume that the named process is done, and we are looking at
      another process, the function returns False in this case.
  """
  try:
    with open('/proc/%d/stat' % pid) as f:
      stat = f.readline().split()
      if ppid is not None and int(stat[3]) != ppid:
        return False
      return stat[2] != 'Z'
  except IOError:
    return False


def CheckCall(*args, **kwargs):
  """Run and wait for the command to be completed.

  It is like subprocess.check_call but with the extra flexibility of Spawn.

  Args/Returns:
    Refer to Spawn.

  Raises:
    process_utils.CalledProcessError if returncode != 0.
  """
  kwargs['check_call'] = True
  return Spawn(*args, **kwargs)


def CheckOutput(*args, **kwargs):
  """Runs command and returns its output.

  It is like subprocess.check_output but with the extra flexibility of Spawn.

  Args:
    Refer to Spawn.

  Returns:
    stdout

  Raises:
    process_utils.CalledProcessError if returncode != 0.
  """
  kwargs['check_output'] = True
  return Spawn(*args, **kwargs).stdout_data


def SpawnOutput(*args, **kwargs):
  """Runs command and returns its output.

  Like CheckOutput. But it won't raise exception unless you set
  check_output=True.

  Args:
    Refer to Spawn.

  Returns:
    stdout
  """
  kwargs['read_stdout'] = True
  return Spawn(*args, **kwargs).stdout_data


def LogAndCheckCall(*args, **kwargs):
  """Logs a command and invokes CheckCall."""
  logging.info('Running: %s', ' '.join(pipes.quote(arg) for arg in args[0]))
  return CheckCall(*args, **kwargs)


def LogAndCheckOutput(*args, **kwargs):
  """Logs a command and invokes CheckOutput."""
  logging.info('Running: %s', ' '.join(pipes.quote(arg) for arg in args[0]))
  return CheckOutput(*args, **kwargs)


class _ExtendedPopen(Popen):
  """Popen subclass supported a few extra methods.

  Attributes:
    stdout_data, stderr_data: Data read by communicate().  These are set by
      the Spawn call if read_stdout/read_stderr are True.
  """
  stdout_data = None
  stderr_data = None

  def stdout_lines(self, strip=False):
    """Returns lines in stdout_data as a list.

    Args:
      strip: If True, each line is stripped.
    """
    return GetLines(self.stdout_data, strip)

  def stderr_lines(self, strip=False):
    """Returns lines in stderr_data as a list.

    Args:
      strip: If True, each line is stripped.
    """
    return GetLines(self.stderr_data, strip)

  # pylint: disable=signature-differs
  def communicate(self, *args, **kwargs):
    if self.stdout_data is None and self.stderr_data is None:
      return super(_ExtendedPopen, self).communicate(*args, **kwargs)
    return self.stdout_data, self.stderr_data


def Spawn(args, **kwargs):
  """Popen wrapper with extra functionality:

    - Sets close_fds to True by default.  (You may still set
      close_fds=False to leave all fds open.)
    - Provides a consistent interface to functionality like the call,
      check_call, and check_output functions in subprocess.

  To get a command's output, logging stderr if the process fails:

    # Doesn't check retcode
    Spawn(['cmd'], read_stdout=True, log_stderr_on_error=True).stdout_data
    # Throws CalledProcessError on error
    Spawn(['cmd'], read_stdout=True, log_stderr_on_error=True,
          check_call=True).stdout_data

  To get a command's stdout and stderr, without checking the retcode:

    stdout, stderr = Spawn(
        ['cmd'], read_stdout=True, read_stderr=True).communicate()

  Args:
    log: Do a logging.info before running the command, or to any
      logging object to call its info method.
    stdout: Same as subprocess.Popen, but may be set to DEV_NULL to discard
      all stdout.
    stderr: Same as subprocess.Popen, but may be set to DEV_NULL to discard
      all stderr.
    call: Wait for the command to complete.
    check_call: Wait for the command to complete, throwing an
      exception if it fails.  This implies call=True.  This may be either
      True to signify that any non-zero exit status is failure, or a function
      that takes a returncode and returns True if that returncode is
      considered OK (e.g., lambda returncode: returncode in [0,1]).
    check_output: Wait for the command to complete, throwing an
      exception if it fails, and saves the contents to the return
      object's stdout_data attribute.  Implies check_call=True and
      read_stdout=True.
    log_stderr_on_error: Log stderr only if the command fails.
      Implies read_stderr=True and call=True.
    read_stdout: Wait for the command to complete, saving the contents
      to the return object's stdout_data attribute.  This implies
      call=True and stdout=PIPE.
    ignore_stdout: Ignore stdout.
    read_stderr: Wait for the command to complete, saving the contents
      to the return object's stderr_data attribute.  This implies
      call=True and stderr=PIPE.
    ignore_stderr: Ignore stderr.
    sudo: Prepend sudo to arguments if user is not root.
    env: Same as subprocess.Popen, set-up environment parameters if needed.
    encoding: Same as subprocess.Popen, we will use `utf-8` as default to make
      it output str type.
    timeout: Set a timeout for process. Implies call=True.

  Returns:
    A _ExtendedPopen object.
  Raises:
    ValueError: If receive wrong arguments.
    CalledProcessError: If check is True and return code is non-zero.
    TimeoutExpired: If timeout expired.
  """
  kwargs.setdefault('close_fds', True)
  kwargs.setdefault('encoding', 'utf-8')

  logger = logging
  log = kwargs.pop('log', False)
  if kwargs.get('shell'):
    args_to_log = args
  else:
    args_to_log = ' '.join(pipes.quote(arg) for arg in args)

  if log:
    if (callable(getattr(log, "info", None)) and
        callable(getattr(log, "error", None))):
      logger = log
    message = 'Running command: "%s"' % args_to_log
    if 'cwd' in kwargs:
      message += ' in %s' % kwargs['cwd']
    logger.info(message)

  call = kwargs.pop('call', False)
  check_call = kwargs.pop('check_call', False)
  check_output = kwargs.pop('check_output', False)
  read_stdout = kwargs.pop('read_stdout', False)
  ignore_stdin = kwargs.pop('ignore_stdin', False)
  ignore_stdout = kwargs.pop('ignore_stdout', False)
  read_stderr = kwargs.pop('read_stderr', False)
  ignore_stderr = kwargs.pop('ignore_stderr', False)
  log_stderr_on_error = kwargs.pop('log_stderr_on_error', False)
  sudo = kwargs.pop('sudo', False)
  timeout = kwargs.pop('timeout', None)

  if sudo and getpass.getuser() != 'root':
    if kwargs.pop('shell', False):
      args = ['sudo', 'sh', '-c', args]
    else:
      args = ['sudo'] + args

  if ignore_stdin:
    assert not kwargs.get('stdin')
    kwargs['stdin'] = DEVNULL
  if ignore_stdout:
    assert not read_stdout
    assert not kwargs.get('stdout')
    kwargs['stdout'] = DEVNULL
  if ignore_stderr:
    assert not read_stderr
    assert not log_stderr_on_error
    assert not kwargs.get('stderr')
    kwargs['stderr'] = DEVNULL

  if check_output:
    check_call = check_call or True
    read_stdout = True
  if check_call:
    call = True
  if log_stderr_on_error:
    read_stderr = True
  if read_stdout:
    call = True
    assert kwargs.get('stdout') in [None, PIPE]
    kwargs['stdout'] = PIPE
  if read_stderr:
    call = True
    assert kwargs.get('stderr') in [None, PIPE]
    kwargs['stderr'] = PIPE
  if timeout:
    call = True

  if call and (not read_stdout) and kwargs.get('stdout') == PIPE:
    raise ValueError('Cannot use call=True argument with stdout=PIPE, '
                     'since OS buffers may get filled up')
  if call and (not read_stderr) and kwargs.get('stderr') == PIPE:
    raise ValueError('Cannot use call=True argument with stderr=PIPE, '
                     'since OS buffers may get filled up')

  process = _ExtendedPopen(args, **kwargs)

  if call:
    try:
      if read_stdout or read_stderr:
        stdout, stderr = process.communicate(timeout=timeout)
        if read_stdout:
          process.stdout_data = stdout
        if read_stderr:
          process.stderr_data = stderr
      else:
        # No need to communicate; just wait
        process.wait(timeout=timeout)
    except TimeoutExpired:
      TerminateOrKillProcess(process)
      raise

    if callable(check_call):
      failed = not check_call(process.returncode)
    else:
      failed = process.returncode != 0
    if failed:
      if log or log_stderr_on_error:
        message = 'Exit code %d from command: "%s"' % (
            process.returncode, args_to_log)
        if log_stderr_on_error:
          message += '; stderr: """\n%s\n"""' % process.stderr_data
        logger.error(message)

      if check_call:
        raise CalledProcessError(process.returncode, args, process.stdout_data,
                                 process.stderr_data)

  return process


class CommandPipe:
  """Interface for commands piping.

  Attributes:
    stdout_data, stderr_data: The data read from the last pipe command.

  Args:
    encoding: If set, all the data read from commands are decoded by it.
    check: If true, raise CalledProcessError if any of commands return non-zero.
    read_timeout: The timeout of each read. This function would block at most
        read_timeout seconds after the process is ended.

  Examples:
    out = CommandPipe().Pipe(['cmdA', 'arg']).Pipe('CmdB').stdout_data
    out, err = CommandPipe().Pipe(['cmdC']).Pipe('CmdD').Communicate()
  """

  def __init__(self, encoding='utf-8', check=True, read_timeout=0.1):
    self._encoding = encoding
    self._check = check
    self._read_timeout = read_timeout
    self._processes = []
    self._is_done = False
    self._stdout_data = None
    self._stderr_data = None

  @property
  def stdout_data(self):
    stdout, unused_stderr = self.Communicate()
    return stdout

  @property
  def stderr_data(self):
    unused_stdout, stderr = self.Communicate()
    return stderr

  def Pipe(self, args, shell=False, sudo=False, env=None):
    """Add a command to the commands pipe.

    Args:
      args: The command to pass to Popen.
      shell, sudo, env: See Spawn().

    Returns:
      self
    """
    if self._is_done:
      raise ValueError(
          'CommandPipe has been fulfilled. Pipe command cannot be added.')

    last_stdout = self._processes[-1].stdout if self._processes else None
    process = Spawn(args, stdin=last_stdout, stdout=PIPE, stderr=PIPE,
                    shell=shell, sudo=sudo, env=env)
    if last_stdout:
      last_stdout.close()
    self._processes.append(process)
    return self

  def _GetDecodedStr(self, string):
    return string.decode(self._encoding) if self._encoding else string

  def _Communicate(self):
    if not self._processes:
      raise ValueError('CommandPipe has no command to run.')

    # `bufs` contains stderr of all the processes, and the stdout of the last
    # process. The last two are the stderr and stdout of the last process.
    out_pipes = ([p.stderr for p in self._processes] +
                 [self._processes[-1].stdout])
    bufs = [b''] * len(out_pipes)
    try:
      while not self._is_done:
        self._is_done = all(p.poll() is not None for p in self._processes)

        rlist, unused_wlist, unused_xlist = select.select(
            out_pipes, [], [], self._read_timeout)
        for i, pipe in enumerate(out_pipes):
          if pipe not in rlist:
            continue

          # Read until the pipe is empty
          pipe_buffer = os.read(pipe.fileno(), 4096)
          while len(pipe_buffer) > 0:
            bufs[i] += pipe_buffer
            pipe_buffer = os.read(pipe.fileno(), 4096)

      self._stdout_data = self._GetDecodedStr(bufs[-1])
      self._stderr_data = self._GetDecodedStr(bufs[-2])

      if self._check:
        for i, p in enumerate(self._processes):
          if p.returncode != 0:
            stdout = (
                self._GetDecodedStr(bufs[-1])
                if p is self._processes[-1] else None)
            stderr = self._GetDecodedStr(bufs[i])
            raise CalledProcessError(p.returncode, p.args, stdout, stderr)
    finally:
      for pipe in out_pipes:
        pipe.close()

  def Communicate(self):
    """Get the output of the commands pipe.

    Returns:
      stdout, stderr: The stdout and stderr of the last command.

    Raises:
      ValueError: No command to be run.
      CalledProcessError: If check is set, and any of the commands failed.
    """
    if not self._is_done:
      self._Communicate()
    return self._stdout_data, self._stderr_data


def TerminateOrKillProcess(process, wait_seconds=1, sudo=False):
  """Terminates a process and waits for it.

  The function sends SIGTERM to terminate the process, if it's not terminated
  in wait_seconds, then sends a SIGKILL.
  """
  pid = process.pid
  logging.debug('Stopping process %d.', pid)

  try:
    if not sudo:
      process.terminate()
    elif process.poll() is None:
      Spawn(['kill', str(pid)], sudo=True, check_call=True, log=True)

    process.wait(wait_seconds)
  except Exception:
    logging.debug('Cannot terminate, sending SIGKILL to process %d.', pid)
    if not sudo:
      process.kill()
    elif process.poll() is None:
      Spawn(['kill', '-SIGKILL', str(pid)], sudo=True, check_call=True,
            log=True)

  logging.debug('Process %d stopped.', pid)


def KillProcessTree(process, caption):
  """Kills a process and all its subprocesses.

  Args:
    process: The process to kill (opened with the subprocess module).
    caption: A caption describing the process.
  """
  # os.kill does not kill child processes. os.killpg kills all processes
  # sharing same group (and is usually used for killing process tree). But in
  # our case, to preserve PGID for autotest and upstart service, we need to
  # iterate through each level until leaf of the tree.

  def get_all_pids(root):
    ps_output = Spawn(['ps', '--no-headers', '-eo', 'pid,ppid'],
                      stdout=subprocess.PIPE)
    children = {}
    for line in ps_output.stdout:
      match = re.findall(r'\d+', line)
      children.setdefault(int(match[1]), []).append(int(match[0]))
    pids = []

    def add_children(pid):
      pids.append(pid)
      list(map(add_children, children.get(pid, [])))
    add_children(root)
    # Reverse the list to first kill children then parents.
    # Note reversed(pids) will return an iterator instead of real list, so
    # we must explicitly call pids.reverse() here.
    pids.reverse()
    return pids

  pids = get_all_pids(process.pid)
  for sig in [signal.SIGTERM, signal.SIGKILL]:
    logging.info('Stopping %s (pid=%s)...', caption, sorted(pids))

    tries = 25
    logging.info('Sending signal %s to %r (tries at most %d)', sig, pids, tries)
    for _ in range(tries):  # 200 ms between tries
      for pid in pids:
        try:
          os.kill(pid, sig)
        except OSError:
          pass
      pids = list(filter(IsProcessAlive, pids))
      if not pids:
        return
      time.sleep(0.2)  # Sleep 200 ms and try again

  logging.warning('Failed to stop %s process %r. Ignoring.', caption, pids)


def WaitEvent(event):
  """Waits for an event without timeout, without blocking signals.

  event.wait() masks all signals until the event is set; this can be used
  instead to make sure that the signal is delivered within 100 ms.

  Returns:
    True if the event is set (i.e., always, since there is no timeout).  This
      return value is used so that this method behaves the same way as
      event.wait().
  """
  while not event.is_set():
    event.wait(0.1)
  return True


def StartDaemonThread(*args, **kwargs):
  """Creates, starts, and returns a daemon thread.

  Args:
    interrupt_when_crash: If true, the thread sends interrupt signal when
        exception uncaught.
    For other parameters see threading.Thread().
  """
  if kwargs.pop('interrupt_on_crash', False):
    # 'target' is the second parameter of threading.Thread()
    target = args[1] if len(args) > 1 else kwargs.get('target')

    def _target(*_args, **_kwargs):
      try:
        target(*_args, **_kwargs)
      except Exception:
        logging.error(traceback.format_exc())
        os.kill(os.getpid(), signal.SIGINT)

    if len(args) > 1:
      args = list(args)
      args[1] = _target
    else:
      kwargs['target'] = _target

  thread = threading.Thread(*args, **kwargs)
  thread.daemon = True
  thread.start()
  return thread


class DummyFile:
  def write(self, x):  # pylint: disable=unused-argument
    pass

  def read(self, x):  # pylint: disable=unused-argument
    return ''


@contextlib.contextmanager
def RedirectStandardStreams(stdin=None, stdout=None, stderr=None):
  """Redirect standard stream.

  Args:
    stdin: A file object to override standard input.
    stdout: A file object to override standard output.
    stderr: A file object to override standard error.
    If stdin, stdout, stderr is None, then the stream is not redirected.

  Raises:
    IOError: raise the exception if the standard streams is redirected again
             within the context.
  """
  args = {'stdin': stdin, 'stdout': stdout, 'stderr': stderr}
  redirect_streams = {k: v for k, v in args.items() if v is not None}
  old_streams = {k: sys.__dict__[k] for k in redirect_streams}

  for k, v in redirect_streams.items():
    sys.__dict__[k] = v

  yield

  changed = {k: sys.__dict__[k] for k, v in redirect_streams.items()
             if v is not sys.__dict__[k]}
  if changed:
    raise IOError('Unexpected standard stream redirections: %r' % changed)
  for k, v in old_streams.items():
    sys.__dict__[k] = v


def PipeStdoutLines(process, callback, read_timeout=0.1):
  """Read a process stdout and call callback for each line of stdout.

  Args:
    process: The process created by Spawn.
    callback: Callback to be executed on each output line. The argument to
        the callback would be the line received.
    read_timeout: The timeout of each read. This function would block at most
        read_timeout seconds after the process is ended.
  """
  buf = ['']

  def _TryReadOutputLines(timeout):
    rlist, unused_wlist, unused_xlist = select.select([process.stdout], [], [],
                                                      timeout)
    if process.stdout not in rlist:
      return False

    # Read a chunk of the process output. This should not block because of the
    # above select, and can return chunk with size < 4096.
    data = str(os.read(process.stdout.fileno(), 4096), 'utf-8')
    if not data:
      return False

    num_lines = data.count('\n')
    buf[0] += data
    for unused_i in range(num_lines):
      line, unused_sep, buf[0] = buf[0].partition('\n')
      callback(line)
    return True

  while process.poll() is None:
    _TryReadOutputLines(read_timeout)

  # Consume all buffered output after the process end.
  while _TryReadOutputLines(0):
    pass

  if process.stdout:
    process.stdout.close()
  if process.stderr:
    process.stderr.close()
