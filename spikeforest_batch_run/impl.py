from kbucket import client as kb
from pairio import client as pa
import random
import string
import datetime

def clearBatch(*,batch_name):
  batch=kb.loadObject(key=dict(batch_name=batch_name))
  jobs=batch['jobs']

  print('Clearing batch {} with {} jobs'.format(batch_name,len(jobs)))
  _clear_job_results(jobs=jobs,incomplete_only=False)


def prepareBatch(*,batch_name):
  batch=kb.loadObject(key=dict(batch_name=batch_name))
  jobs=batch['jobs']

  print('Preparing batch {} with {} jobs'.format(batch_name,len(jobs)))
  _clear_job_results(jobs=jobs,incomplete_only=True)
  _download_recordings(jobs=jobs)

def runBatch(*,batch_name):
  batch=kb.loadObject(key=dict(batch_name=batch_name))
  jobs=batch['jobs']

  print('Running batch {} with {} jobs'.format(batch_name,len(jobs)))
  for job in jobs:
    _run_job(job)

def _do_sort_recording(job):
  try:
    from .sort_recording import sort_recording
  except:
    print('Problem importing sort_recording. You probably need to install one or more python packages.')
    raise
  return sort_recording(sorter=job['sorter'],recording=job['recording'])

def _do_summarize_recording(job):
  try:
    from .summarize_recording import summarize_recording
  except:
    print('Problem importing summarize_recording. You probably need to install one or more python packages.')
    raise
  return summarize_recording(recording=job['recording'])

def _do_run_job(job):
  if job['command']=='sort_recording':
    return _do_sort_recording(job)
  elif job['command']=='summarize_recording':
    return _do_summarize_recording(job)
  else:
    return dict(error='Invalid job command: '+job['command'])

def _set_job_status(job,status):
  kb.saveObject(key=dict(name='job_status',job=job),object=status)

def _run_job(job):
  val=pa.get(key=job)
  if val:
    return
  code=''.join(random.choice(string.ascii_uppercase) for x in range(10))
  if not pa.set(key=job,value='in-process-'+code,overwrite=False):
    return
  status=dict(
    time_started=_make_timestamp(),
    status='running'
  )
  _set_job_status(job,status)

  print('Running job: '+job['label'])
  try:
    result=_do_run_job(job)
  except:
    status['time_finished']=_make_timestamp()
    status['status']='error'
    status['error']='Exception in _do_run_job'
    val=pa.get(key=job)
    if val=='in-process-'+code:
      _set_job_status(job,status)  
    raise

  val=pa.get(key=job)
  if val!='in-process-'+code:
    print('Not saving result because in-process code does not match {} <> {}.'.format(val,'in-process-'+code))
    return

  status['time_finished']=_make_timestamp()
  status['result']=result
  if 'error' in result:
    print('Error running job: '+result['error'])
    status['status']='error'
    status['error']=result['error']
    _set_job_status(job,status)
    pa.set(key=job,value='error-'+code)
    return
  status['status']='finished'
  kb.saveObject(key=job,object=result) # Not needed in future, because we should instead use the status object

def assembleBatchResults(*,batch_name):
  batch=kb.loadObject(key=dict(batch_name=batch_name))
  jobs=batch['jobs']

  print('Assembling results for batch {} with {} jobs'.format(batch_name,len(jobs)))
  job_results=[]
  for job in jobs:
    print('ASSEMBLING: '+job['label'])
    result=kb.loadObject(key=job)
    if not result:
      raise Exception('Unable to load object for job: '+job['label'])
    job_results.append(dict(
        job=job,
        result=result
    ))
  print('Saving results...')
  kb.saveObject(key=dict(name='job_results',batch_name=batch_name),object=dict(job_results=job_results))
  print('Done.')

def _clear_job_results(*,jobs,incomplete_only=True):
  for job in jobs:
    val=pa.get(key=job)
    if val:
      if (not incomplete_only) or (val.startswith('in-process')) or (val.startswith('error')):
        print('Clearing job: '+job['label'])
        pa.set(key=job,value=None)

def _download_recordings(*,jobs):
  for job in jobs:
    val=pa.get(key=job)
    if not val:
      if 'recording' in job:
        if 'directory' in job['recording']:
          dsdir=job['recording']['directory']
          fname=dsdir+'/raw.mda'
          print('REALIZING FILE: '+fname)
          kb.realizeFile(fname)

def _make_timestamp():
  return str(datetime.datetime.now())