using System;
using System.Collections.Generic;

public class ThreadSafeScheduler
{
    private readonly object _eventsLock = new object();
    private bool _eventsPending;
    private readonly Queue<Action> _events = new Queue<Action>();

    public void Enqueue(Action action)
    {
        lock (_eventsLock)
        {
            _events.Enqueue(action);
            _eventsPending = true;
        }
    }

    public void Update()
    {
        if (!_eventsPending) return;

        lock (_eventsLock)
        {
            while (_events.Count > 0)
                _events.Dequeue().Invoke();
            _eventsPending = false;
        }
    }
}
