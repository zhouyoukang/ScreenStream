// #define LOG_SOCKET_DATA
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
// ReSharper disable InconsistentNaming
#pragma warning disable SYSLIB0021
#pragma warning disable SYSLIB0023

public interface ISocket
{
    bool Connected { get; }
    IPEndPoint Endpoint { get; }
    void Connect();
    void Send(byte[] bytes);
    int Receive(byte[] buffer);
    int Receive(byte[] buffer, int offset, int size, SocketFlags flags);
    void Shutdown(SocketShutdown how);
    void Close();
}

public class SocketWrapper : ISocket
{
    private readonly IPEndPoint _endpoint;
    private readonly Socket _socket;

    public IPEndPoint Endpoint => _endpoint;
    public bool Connected => _socket.Connected;

    public SocketWrapper(IPEndPoint endpoint)
    {
        _endpoint = endpoint;
        _socket = new Socket(_endpoint.AddressFamily, SocketType.Stream, ProtocolType.Tcp);
    }

    public void Connect()
    {
        _socket.Connect(_endpoint);
    }

    public void Send(byte[] bytes)
    {
        _socket.Send(bytes);
    }

    public int Receive(byte[] buffer)
    {
        return _socket.Receive(buffer);
    }

    public int Receive(byte[] buffer, int offset, int size, SocketFlags flags)
    {
        return _socket.Receive(buffer, offset, size, flags);
    }

    public void Shutdown(SocketShutdown how)
    {
        _socket.Shutdown(how);
    }

    public void Close()
    {
        _socket.Close();
    }
}

public interface ISocketFactory
{
    ISocket Create();
}

public class SocketFactory : ISocketFactory
{
    private readonly IPEndPoint _endpoint;

    public SocketFactory(IPEndPoint endpoint)
    {
        _endpoint = endpoint;
    }

    public ISocket Create()
    {
        return new SocketWrapper(_endpoint);
    }
}

public class WebSocketClient : IDisposable
{
    private static readonly Random _random = new Random();
    private readonly byte[] _buffer = new byte[2048];
    private readonly ISocketFactory _socketFactory;
    private readonly string _token;
    private byte[] _continuationBuffer = new byte[4096];
    private int _remainingBufferOffset;
    private int _remainingBufferLength;
    private ISocket _socket;
    private bool _sentCloseFrame;

    public bool Connected => _socket.Connected;

    public WebSocketClient(IPEndPoint endpoint, string token)
        : this(new SocketFactory(endpoint), token)
    {
    }

    public WebSocketClient(ISocketFactory socketFactory, string token)
    {
        _socketFactory = socketFactory;
        _token = token;
    }

    public void Connect()
    {
        ConnectSocket();

        Handshake();
    }

    private void ConnectSocket()
    {
        _sentCloseFrame = false;
        _socket = _socketFactory.Create();
        _socket.Connect();
    }

    private void Handshake()
    {
        var secWebSocketKey = GenerateWebSocketHandshakeSecurityKey();
        var handshakeRequest = BuildHandshakeRequest(secWebSocketKey);
        _socket.Send(Encoding.UTF8.GetBytes(handshakeRequest));
        var buffer = new byte[8192];
        var bytesReceived = _socket.Receive(buffer);
        if (bytesReceived > buffer.Length)
            throw new InvalidOperationException("Buffer too small to receive handshake response.");
        var response = Encoding.UTF8.GetString(buffer, 0, bytesReceived);
        var responseLines = response.Split('\r', '\n');
        /* EXAMPLE:
        HTTP/1.1 101 Switching Protocols
        Connection: Upgrade
        Date: Tue, 13 Jun 2023 20:16:25 GMT
        Server: Kestrel
        Upgrade: websocket
        Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
        */
        if (responseLines[0].StartsWith("HTTP/1.1 400"))
            throw new InvalidOperationException("Bad request (400). Verify that your API key is correct and that the host is configured correctly.");
        if (responseLines[0].StartsWith("HTTP/1.1 401"))
            throw new InvalidOperationException("Unauthorized access (401). Please provide a valid API key and make sure the host is correct.");
        if (responseLines[0].StartsWith("HTTP/1.1 403"))
            throw new InvalidOperationException("Forbidden (403). Please provide a valid API key and make sure the host is correct.");
        if (responseLines[0].StartsWith("HTTP/1.1 404"))
            throw new InvalidOperationException("Service not found (404). Make sure the host is correct.");
        if (responseLines[0].StartsWith("HTTP/1.1 500"))
            throw new InvalidOperationException("Internal server error (500). Check the server logs for more details.\r\n" + response);
        if (!responseLines[0].StartsWith("HTTP/1.1 101"))
            throw new InvalidOperationException("Attempt to connect to a web server that does not support web sockets. Server returned:\r\n" + response);
        if (responseLines.Length < 4)
            throw new InvalidOperationException("Attempt to connect to a web server that does not support web sockets. Server returned:\r\n" + response);
        var secWebSocketAccept = responseLines
            .FirstOrDefault(h => h.StartsWith("Sec-WebSocket-Accept: ", StringComparison.OrdinalIgnoreCase))?
            .Substring("Sec-WebSocket-Accept: ".Length)
            .Trim();
        if (secWebSocketAccept == "")
            throw new InvalidOperationException("Sec-WebSocket-Accept header value was not found.");
        var expectedSecWebSocketAccept = ComputeWebSocketHandshakeSecurityHash(secWebSocketKey);

        if (!expectedSecWebSocketAccept.Equals(secWebSocketAccept, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Sec-WebSocket-Accept header value doesn't match the computed value.");
    }

    private string BuildHandshakeRequest(string secWebSocketKey)
    {
        var handshakeRequest =
            "GET /hub HTTP/1.1\r\n" +
            "Host: " + _socket.Endpoint + "\r\n" +
            "Upgrade: websocket\r\n" +
            "Connection: Upgrade\r\n" +
            "Sec-WebSocket-Key: " + secWebSocketKey + "\r\n" +
            "Sec-WebSocket-Version: 13\r\n";
        if(!string.IsNullOrEmpty(_token))
            handshakeRequest += $"Authorization: Bearer {_token}\r\n";
        handshakeRequest += "\r\n";
        return handshakeRequest;
    }

    private static string GenerateWebSocketHandshakeSecurityKey()
    {
        var rng = new RNGCryptoServiceProvider();
        var key = new byte[16];
        rng.GetBytes(key);
        return Convert.ToBase64String(key);
    }

    private static string ComputeWebSocketHandshakeSecurityHash(string secWebSocketKey)
    {
        const string webSocketGuid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
        var combined = secWebSocketKey + webSocketGuid;
        var sha1Provider = new SHA1CryptoServiceProvider();
        var sha1Hash = sha1Provider.ComputeHash(Encoding.UTF8.GetBytes(combined));
        return Convert.ToBase64String(sha1Hash);
    }

    public void Disconnect()
    {
        if (_socket?.Connected != true) return;
        SendCloseFrame(true);
    }

    public IEnumerable<string> ReadResponse()
    {
        do
        {
            int bytesReceived;
            int bufferLength;
            if (_remainingBufferLength > 0)
            {
                bufferLength = _remainingBufferLength;
                bytesReceived = _remainingBufferLength;
                Array.Copy(_buffer, _remainingBufferOffset, _buffer, 0, _remainingBufferLength);
                _remainingBufferOffset = 0;
                _remainingBufferLength = 0;
            }
            else
            {
                bufferLength = _buffer.Length;
                bytesReceived = _socket.Receive(_buffer);
                if (bytesReceived == 0) yield break;
            }

            var opcode = (_buffer[0] & 0x0f);
            var isFinalFrame = (_buffer[0] & 0x80) != 0;
            var initialPayloadLength = _buffer[1] & 0x7f;

            // Determine required header length
            int headerLength;
            if (initialPayloadLength == 126)
                headerLength = 4;
            else if (initialPayloadLength == 127)
                headerLength = 10;
            else
                headerLength = 2;

            // Ensure the entire header is read
            if (bytesReceived < headerLength)
            {
                int bytesNeeded = headerLength - bytesReceived;
                int totalRead = bytesReceived;
                while (bytesNeeded > 0)
                {
                    int read = _socket.Receive(_buffer, totalRead, bytesNeeded, SocketFlags.None);
                    if (read == 0) throw new InvalidOperationException("Unexpected end of stream while reading header");
                    totalRead += read;
                    bytesNeeded -= read;
                }
                bytesReceived = totalRead;
            }

            int payloadLength;
            int payloadStartIndex;
            GetPayloadLength(initialPayloadLength, 0, out payloadLength, out payloadStartIndex);

            #if(LOG_SOCKET_DATA)
            {
                var message = $"Received {bytesReceived} bytes: {Convert.ToBase64String(_buffer, 0, bytesReceived)}";
                ThreadSafeLogger.Current.Error(() => message);
            }
            #endif

            switch (opcode)
            {
                case WebSocketOpcode.ConnectionClose:
                    if (!_sentCloseFrame)
                        SendCloseFrame(false);
                    _socket.Shutdown(SocketShutdown.Both);
                    _socket.Close();
                    yield break;
                case WebSocketOpcode.Ping:
                    var pongPayload = new byte[payloadLength];
                    Array.Copy(_buffer, payloadStartIndex, pongPayload, 0, pongPayload.Length);
                    SendPongFrame(pongPayload);
                    continue;
                case WebSocketOpcode.Pong:
                case WebSocketOpcode.UnsolicitedPong:
                    continue;
                case WebSocketOpcode.ContinuationFrame:
                case WebSocketOpcode.TextFrame:
                case WebSocketOpcode.BinaryFrame:
                    ReadPayloadIntoContinuationBuffer(payloadStartIndex, payloadLength, bytesReceived, bufferLength);
                    var str = Encoding.UTF8.GetString(_continuationBuffer, 0, payloadLength);
                    yield return str;
                    if (!isFinalFrame)
                        continue;
                    break;
                default:
                    throw new NotImplementedException($"OpCode {opcode} not implemented");
            }

            yield break;
        } while (true);
    }

    private void ReadPayloadIntoContinuationBuffer(int payloadStartIndex, int payloadLength, int initialReceivedBytes, int bufferLength)
    {
        var bufferedPayloadLength = bufferLength - payloadStartIndex;
        ResizeBuffer(payloadLength);
        if (bufferedPayloadLength < 0)
            throw new InvalidOperationException($"Buffered payload length is negative. Buffer length: {bufferLength}, payload start index: {payloadStartIndex}, payload length: {payloadLength}");
        Array.Copy(_buffer, payloadStartIndex, _continuationBuffer, 0, Math.Min(payloadLength, bufferedPayloadLength));

        // Buffer too small, read more bytes
        if (payloadLength > bufferedPayloadLength)
        {
            var continuationBufferIndex = bufferedPayloadLength;
            var remainingBytes = payloadLength - bufferedPayloadLength;
            while (remainingBytes > 0)
            {
                var bytesReceived = _socket.Receive(_buffer, 0, Math.Min(remainingBytes, _buffer.Length), SocketFlags.None);
                if (bytesReceived == 0) throw new InvalidOperationException("Received no bytes while reading buffer overflow");
                Array.Copy(_buffer, 0, _continuationBuffer, continuationBufferIndex, bytesReceived);
                remainingBytes -= bytesReceived;
                continuationBufferIndex += bytesReceived;

                #if(LOG_SOCKET_DATA)
                {
                    var message = $"Received {bytesReceived} continuation bytes: {Convert.ToBase64String(_buffer, 0, bytesReceived)}";
                    ThreadSafeLogger.Current.Error(() => message);
                }
                #endif
            }
        }
        else
        {
            _remainingBufferOffset = payloadStartIndex + payloadLength;
            _remainingBufferLength = initialReceivedBytes - _remainingBufferOffset;
        }
    }

    private void ResizeBuffer(int neededLength)
    {
        if (neededLength <= _continuationBuffer.Length) return;
        var desiredLength = _continuationBuffer.Length;
        while (desiredLength < neededLength) desiredLength *= 2;
        Array.Resize(ref _continuationBuffer, desiredLength);
    }

    private void GetPayloadLength(int initialPayloadLength, int bufferOffset, out int payloadLength, out int payloadStartIndex)
    {
        if (initialPayloadLength <= 125)
        {
            payloadLength = initialPayloadLength;
            payloadStartIndex = 2;
        }
        else if (initialPayloadLength == 126)
        {
            payloadLength = BitConverter.ToUInt16(new[] { _buffer[bufferOffset + 3], _buffer[bufferOffset + 2] }, 0);
            payloadStartIndex = 4;
        }
        else if (initialPayloadLength == 127)
        {
            payloadLength = (int)BitConverter.ToUInt64(
                new[]
                {
                    _buffer[bufferOffset + 9], _buffer[bufferOffset + 8], _buffer[bufferOffset + 7], _buffer[bufferOffset + 6], _buffer[bufferOffset + 5], _buffer[bufferOffset + 4],
                    _buffer[bufferOffset + 3], _buffer[bufferOffset + 2]
                }, 0);
            payloadStartIndex = 10;
        }
        else
        {
            throw new Exception("Invalid payload length value.");
        }
    }

    public void SendMessage(string message)
    {
        var payload = Encoding.UTF8.GetBytes(message);
        var framedMessage = FrameMessage(payload, WebSocketOpcode.TextFrame, true);
        _socket.Send(framedMessage);
    }

    private static readonly byte[] _maskingKey = new byte[4];

    private static byte[] FrameMessage(byte[] payload, byte opcode, bool isFinalFrame)
    {
        // Determine the size of the payload length field
        var payloadLengthSize = payload.Length <= 125 ? 0 :
            payload.Length <= ushort.MaxValue ? 2 : 8;

        // Total frame size: 2 bytes for headers, 4 bytes for mask key, payload length field, and the payload
        var frame = new byte[2 + 4 + payloadLengthSize + payload.Length];

        // First byte: FIN bit and opcode
        frame[0] = (byte)((isFinalFrame ? 0x80 : 0x00) | opcode);

        // Second byte and extended payload length if necessary
        if (payloadLengthSize == 0)
        {
            frame[1] = (byte)(0x80 | payload.Length); // Mask bit and payload length (<= 125)
        }
        else if (payloadLengthSize == 2)
        {
            frame[1] = 0x80 | 126; // Mask bit and payload length indicator for 16 bit length
            var lengthBytes = BitConverter.GetBytes((ushort)IPAddress.HostToNetworkOrder((short)payload.Length));
            Buffer.BlockCopy(lengthBytes, 0, frame, 2, 2);
        }
        else // payloadLengthSize == 8
        {
            frame[1] = 0x80 | 127; // Mask bit and payload length indicator for 64 bit length
            var lengthBytes = BitConverter.GetBytes(IPAddress.HostToNetworkOrder((long)payload.Length));
            Buffer.BlockCopy(lengthBytes, 0, frame, 2, 8);
        }

        // Calculate the offset where the payload starts after the mask key
        int payloadOffset = 2 + payloadLengthSize + 4;

        WriteMasked(payload, frame, payloadOffset);

        return frame;
    }

    private static void WriteMasked(byte[] payload, byte[] frame, int offset)
    {
        // Generate a random masking key
        _random.NextBytes(_maskingKey);
        // Copy the masking key to the frame
        Buffer.BlockCopy(_maskingKey, 0, frame, offset - 4, 4);

        // Apply the masking key to the payload data and copy it into the frame
        for (var i = 0; i < payload.Length; i++)
        {
            frame[offset + i] = (byte)(payload[i] ^ _maskingKey[i % 4]);
        }
    }

    private void SendCloseFrame(bool initiator)
    {
        if (_socket == null || !_socket.Connected) return;

        _socket.Send(initiator
            ? new byte[] { 0x88, 0x80, 0x00, 0x00, 0x00, 0x00 }
            : new byte[] { 0x88, 0x00 }
        );
    }

    private void SendPongFrame(byte[] payload)
    {
        if (_socket == null || !_socket.Connected) return;
        var frame = FrameMessage(payload, WebSocketOpcode.Pong, true);
        _socket.Send(frame);
    }

    private static class WebSocketOpcode
    {
        public const byte ContinuationFrame = 0x0;
        public const byte TextFrame = 0x1;
        // ReSharper disable once UnusedMember.Local
        public const byte BinaryFrame = 0x2;
        public const byte UnsolicitedPong = 0x5;
        public const byte ConnectionClose = 0x8;
        public const byte Ping = 0x9;
        public const byte Pong = 0xA;
    }

    public void Dispose()
    {
        try
        {
            if (_socket == null || !_socket.Connected) return;
            _socket.Shutdown(SocketShutdown.Both);
            _socket.Close();
        }
        catch
        {
            // ignore
        }
    }
}
