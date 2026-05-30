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
      };
      
      ws.current.onclose = () => {
        setStatus('disconnected');
      };
      
      ws.current.onerror = () => {
        setError(new Error('WebSocket error occurred'));
        notifyListeners(JSON.stringify({ status: 'ERROR', message: 'Connection Error', step: 'error' }));
      };
      
      ws.current.onmessage = (event) => {
        const dataStr = typeof event.data === 'string' ? event.data : JSON.stringify(event.data);
        notifyListeners(dataStr);
      };
    } catch (err) {
      setStatus('disconnected');
      setError(err instanceof Error ? err : new Error('Unknown error'));
      notifyListeners(JSON.stringify({ status: 'ERROR', message: `Failed to connect: ${err}`, step: 'error' }));
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
      notifyListeners(JSON.stringify({ status: 'ERROR', message: 'Cannot send message, not connected.', step: 'error' }));
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
