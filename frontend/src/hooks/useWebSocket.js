/**
 * WebSocket Hook for Real-Time Updates
 */

import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = process.env.REACT_APP_BACKEND_URL?.replace('http', 'ws').replace('/api', '') + '/ws';
const ENABLE_WS = process.env.REACT_APP_BACKEND_URL?.includes('localhost') || process.env.REACT_APP_BACKEND_URL?.includes('127.0.0.1');

export const useWebSocket = (onMessage) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connect = useCallback(() => {
    // Skip WebSocket connection if using public Kalshi API (only enable for localhost/internal backends)
    if (!ENABLE_WS) {
      console.log('WebSocket disabled for public API');
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      wsRef.current = new WebSocket(WS_URL);

      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastUpdate(new Date());
          if (onMessage) onMessage(data);
        } catch (e) {
          console.error('Error parsing WebSocket message:', e);
        }
      };

      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        // Attempt reconnect after 5 seconds (only if enabled)
        if (ENABLE_WS) {
          reconnectTimeoutRef.current = setTimeout(connect, 5000);
        }
      };

      wsRef.current.onerror = (error) => {
        console.debug('WebSocket error (expected for public API):', error);
      };
    } catch (e) {
      console.debug('WebSocket connection attempt failed (expected for public API):', e);
    }
  }, [onMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
    }
  }, []);

  const sendMessage = useCallback((message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { isConnected, lastUpdate, sendMessage, reconnect: connect };
};

export default useWebSocket;
