import { useEffect, useRef, useState } from 'react';

type WebSocketStatus = 'disconnected' | 'connecting' | 'connected';

export function useWebSocket(url: string | null) {
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const [error, setError] = useState<Error | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const listeners = useRef<((data: string) => void)[]>([]);

  const connect = () => {
    if (!url || ws.current?.readyState === WebSocket.OPEN) return;
    
    try {
      setStatus('connecting');
      ws.current = new WebSocket(url);
      
      ws.current.onopen = () => {
        setStatus('connected');
        setError(null);
        notifyListeners(`\x1b[32m[SYSTEM] Connected to job stream: ${url}\x1b[0m\r\n`);
      };
      
      ws.current.onclose = () => {
        setStatus('disconnected');
        notifyListeners(`\x1b[33m[SYSTEM] Disconnected from stream\x1b[0m\r\n`);
      };
      
      ws.current.onerror = () => {
        setError(new Error('WebSocket error occurred'));
        notifyListeners(`\x1b[31m[SYSTEM] Connection Error\x1b[0m\r\n`);
      };
      
      ws.current.onmessage = (event) => {
        const dataStr = typeof event.data === 'string' ? event.data : JSON.stringify(event.data);
        notifyListeners(dataStr);
      };
    } catch (err) {
      setStatus('disconnected');
      setError(err instanceof Error ? err : new Error('Unknown error'));
      notifyListeners(`\x1b[31m[SYSTEM] Failed to connect: ${err}\x1b[0m\r\n`);
    }
  };

  const disconnect = () => {
    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }
  };

  const notifyListeners = (data: string) => {
    listeners.current.forEach(listener => listener(data));
  };

  const subscribe = (listener: (data: string) => void) => {
    listeners.current.push(listener);
    return () => {
      listeners.current = listeners.current.filter(l => l !== listener);
    };
  };

  const sendMessage = (message: string) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(message);
    } else {
      notifyListeners(`\x1b[31m[SYSTEM] Cannot send message, not connected.\x1b[0m\r\n`);
    }
  };

  useEffect(() => {
    if (url) {
      connect();
    }
    
    return () => {
      disconnect();
    };
  }, [url]);

  return { status, error, connect, disconnect, subscribe, sendMessage, notifyListeners };
}
