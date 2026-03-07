using System;
using System.Threading;
using UnityEngine;

public sealed class ThreadSafeLogger
{
    private readonly ThreadSafeScheduler _scheduler;
    private readonly JSONStorableBool _enableLogs;
    private readonly Thread _mainThread;

    public ThreadSafeLogger(ThreadSafeScheduler scheduler, JSONStorableBool enableLogs)
    {
        _mainThread = Thread.CurrentThread;
        _scheduler = scheduler;
        _enableLogs = enableLogs;
    }

    public bool Enabled => _enableLogs.val;

    public void Log(Func<string> message)
    {
        if (!_enableLogs.val) return;
        var formatted = FormatMessage(message);
        Log(formatted);
    }

    private void Log(string message)
    {
        if (!_enableLogs.val) return;
        if (Thread.CurrentThread == _mainThread)
            SuperController.LogMessage(message);
        else
            _scheduler.Enqueue(() => SuperController.LogMessage(message));
    }

    public void Error(Func<string> message)
    {
        var formatted = FormatMessage(message);
        if (Thread.CurrentThread == _mainThread)
            SuperController.LogError(formatted);
        else
            _scheduler.Enqueue(() => SuperController.LogError(formatted));
    }

    private static string FormatMessage(Func<string> message)
    {
        return $"[{Time.realtimeSinceStartup:0.00}] Voxta: {message()}";
    }
}
