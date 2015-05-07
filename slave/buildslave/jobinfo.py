import datetime
import sys

import psutil

if sys.platform == "win32":
    import win32job


def get_job_info(job, buildbot_process):
    process_list = win32job.QueryInformationJobObject(job,
        win32job.JobObjectBasicProcessIdList)
    return print_process_tree(process_list, buildbot_process)


def get_proc_info(pid, buildbot_process):
    process = psutil.Process(pid)
    process_list = [p.pid for p in process.children(recursive=True)]
    return print_process_tree(process_list, buildbot_process)


def get_process_attr(proc, attr):
    """
    Returns a process attr and is robush to NoSuchProcessError
    """
    try:
        return getattr(proc, attr)()
    except psutil.NoSuchProcess:
        if attr == "cpu_times":
            return ("", "")
        elif attr == "create_time":
            return 0
        return ""


def print_process_tree(process_list, buildbot_process):
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
        elif process.parent() is not None:
            proc_tree.setdefault(process.parent().pid, []).append(process)
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
            msg += " Name: [%s]" % get_process_attr(pidobj, "name")
            msg += " Command line: [%s]" % ' '.join(
                get_process_attr(pidobj, "cmdline"))
            try:
                msg += " Parent PID: [%s]" % pidobj.parent().pid
            except:
                msg += " Parent PID: Not found"
            msg += " Status: [%s]" % get_process_attr(pidobj, "status")
            creation_time = get_process_attr(pidobj, "create_time")
            if creation_time:
                datetime.datetime.fromtimestamp(
                    creation_time).strftime("%Y-%m-%d %H:%M:%S")
            msg += " Creation Time: [%s]" % creation_time
            (user, systime) = get_process_attr(pidobj, "cpu_times")
            msg += " User: [%s] Sys: [%s]" % (user, systime)
            level = level_map.get(pid, level)
            line = "^ " * level
            line += msg
            line += "\n"
            buildbot_process.sendStatus({"header": line})
            text += line
            if proc_tree.get(pid, "") != "":
                if len(stack) > 0 and int(stack[0].pid) not in level_map:
                    level_map[int(stack[0].pid)] = level
                stack = proc_tree[pid] + stack
                level = level + 1
    return text
