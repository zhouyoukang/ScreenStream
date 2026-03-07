using System;
using System.Collections;
using System.Collections.Generic;
using MVR.FileManagementSecure;
using UnityEngine;
using UnityEngine.Events;
using Object = UnityEngine.Object;


public class SpeechPlayback : IDisposable
{
    public class SpeechPlaybackItem
    {
        public string Url { get; set; }
        public VoxtaClient.MessageChunk Chunk { get; set; }
        public VoxtaClient.MessageEnd End { get; set; }
        public AudioSourceControl AudioSource { get; set; }
        public float Duration { get; set; }
    }

    public readonly SpeechPlaybackItemUnityEvent OnPlaybackStarting = new SpeechPlaybackItemUnityEvent();
    public readonly VoxtaClient.StringUnityEvent OnPlaybackCompleted = new VoxtaClient.StringUnityEvent();

    private readonly MonoBehaviour _owner;
    private readonly VoxtaCredentials _credentials;
    private readonly ThreadSafeLogger _logger;

    private readonly Queue<SpeechPlaybackItem> _playbackQueue = new Queue<SpeechPlaybackItem>();

    private Coroutine _playCo;
    private string _currentMessageId;
    private bool _playing;
    private float _lastAudioEnd;

    public SpeechPlayback(MonoBehaviour owner, VoxtaCredentials credentials, ThreadSafeLogger logger)
    {
        _owner = owner;
        _credentials = credentials;
        _logger = logger;
    }

    public void Start(string messageId)
    {
        _currentMessageId = messageId;
    }

    public void Interrupt()
    {
        var wasPlaying = _playing;

        if (_playCo != null)
        {
            _owner.StopCoroutine(_playCo);
            _playCo = null;
        }

        while (_playbackQueue.Count > 0)
        {
            var item = _playbackQueue.Dequeue();
            if (item.End != null)
                OnPlaybackCompleted.Invoke(item.End.MessageId);
        }

        _playing = false;

        if (wasPlaying)
            _logger.Log(() => "Interrupting speech playback");
    }

    public void EnqueuePlay(VoxtaClient.MessageChunk chunk, AudioSourceControl audioSource)
    {
        if (string.IsNullOrEmpty(chunk.AudioUrl)) return;

        _playbackQueue.Enqueue(new SpeechPlaybackItem
        {
            Chunk = chunk,
            Url = GetCompleteUrl(chunk.AudioUrl),
            AudioSource = audioSource,
        });

        if (_playCo == null)
        {
            _playCo = _owner.StartCoroutine(PlayCo());
        }
    }

    public void EnqueueComplete(VoxtaClient.MessageEnd end)
    {
        _playbackQueue.Enqueue(new SpeechPlaybackItem
        {
            End = end,
        });

        if (_playCo == null)
        {
            _playCo = _owner.StartCoroutine(PlayCo());
        }
    }

    private IEnumerator PlayCo()
    {
        try
        {
            while (_playbackQueue.Count > 0)
            {
                var item = _playbackQueue.Dequeue();
                // Waiting a frame to avoid breaking the UI loop
                yield return 0;

                if (item.End != null)
                {
                    OnPlaybackCompleted.Invoke(item.End.MessageId);
                    continue;
                }

                if (string.IsNullOrEmpty(item.Url) || item.AudioSource == null)
                {
                    continue;
                }

                AudioClip clip;
                if(item.Chunk != null)
                {
                    var url = item.Url;
                    if (item.Chunk.MessageId != _currentMessageId) continue;
                    clip = ImportClip(url);
                    if (clip == null) continue;
                }
                else
                {
                    _logger.Error(() => $"Playback item without chunk: {_currentMessageId}");
                    continue;
                }

                var audioSource = item.AudioSource;
                if (audioSource == null) continue;

                if (item.Chunk.AudioGapMs.HasValue)
                {
                    var gap = item.Chunk.AudioGapMs.Value / 1000f;
                    var timeSinceLastAudioEnd = Time.realtimeSinceStartup - _lastAudioEnd;
                    if (timeSinceLastAudioEnd < gap)
                    {
                        yield return new WaitForSeconds(gap - timeSinceLastAudioEnd);
                    }
                }

                audioSource.StopAndClearQueue();
                audioSource.audioSource.clip = clip;
                audioSource.audioSource.Play();
                item.Duration = audioSource.audioSource.pitch == 0 ? 0 : (audioSource.audioSource.clip?.length ?? 0f) / audioSource.audioSource.pitch;
                if(item.Duration == 0)
                    _logger.Error(() => $"Speech playback duration is 0: {item.Url}");
                _playing = true;
                OnPlaybackStarting.Invoke(item);
                while (audioSource.audioSource.isPlaying || SuperController.singleton.freezeAnimation)
                {
                    yield return new WaitForSeconds(0.1f);
                }

                _lastAudioEnd = Time.realtimeSinceStartup;
                _playing = false;
                if (audioSource.audioSource.clip == clip)
                    audioSource.audioSource.clip = null;
                Object.Destroy(clip);
            }
        }
        finally
        {
            _playCo = null;
        }
    }

    private static AudioClip ImportClip(string url)
    {
        if (url.EndsWith(".wav"))
        {
            var wav = new WAV(FileManagerSecure.ReadAllBytes(url));
            return NAudioPlayer.AudioClipFromWAV(wav);
        }

        SuperController.LogError($"Voxta: Cannot load '{url}': This extension is not supported in Virt-A-Mate");
        return null;
    }

    public void Dispose()
    {
        if (_playCo != null)
            _owner.StopCoroutine(_playCo);
    }

    private string GetCompleteUrl(string url)
    {
        if (url.StartsWith("/"))
            url = _credentials.BaseUrl + url;
        return url;
    }

    public class SpeechPlaybackItemUnityEvent : UnityEvent<SpeechPlaybackItem> { }
}
