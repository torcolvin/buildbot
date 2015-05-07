import win32job
import psutil
import datetime
from twisted.python import log


def getJobInfo(job, buildbot_process):
    process_list = win32job.QueryInformationJobObject(job,
                                                      win32job.JobObjectBasicProcessIdList)
    text = ""
    msg = ""
    proc_tree = {}
    base_pids = []
    for pid in process_list:
        pid = int(pid)
        try:
            process = psutil.Process(pid)
        except psutil.error.NoSuchProcess:
            process = None
        if not process:
            text += "pid %s already exited\n" % pid
            continue
        if not base_pids:
            base_pids.append(process)
        elif process.parent != None:
            proc_tree.setdefault(process.parent.pid, []).append(process)
        else:
            base_pids.append(process)

    for base_pid in base_pids:
        stack = [base_pid]
        level = 0
        level_map = {}
        while len(stack) > 0:
            pidobj = stack.pop(0)
            pid = int(pidobj.pid)
            msg = "%s" % pid
            msg += " Name: [%s]" % pidobj.name
            msg += " Command line: [%s]" % ' '.join(pidobj.cmdline)
            try:
                msg += " Parent PID: [%s]" % pidobj.parent.pid
            except:
                msg += " Parent PID: Not found"
            msg += " Status: [%s]" % pidobj.status
            msg += " Creation Time: [%s]" % \
                datetime.datetime.fromtimestamp(
                    pidobj.create_time).strftime("%Y-%m-%d %H:%M:%S")
            (user, systime) = pidobj.get_cpu_times()
            msg += " User: [%s] Sys: [%s]" % (user, systime)
            level = level_map.get(pid, level)
            line = "^ " * level
            line += msg
            line += "\n"
            buildbot_process.sendStatus({"header": line})
            text += line
            if proc_tree.get(pid, "") != "":
                if len(stack) > 0 and level_map.get(int(stack[0].pid), "") == "":
                    level_map[int(stack[0].pid)] = level
                stack = proc_tree[pid] + stack
                level = level + 1
    return text
