import { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import './TerminalUI.css';

interface TerminalUIProps {
  subscribe: (listener: (data: string) => void) => () => void;
  height?: string;
}

export function TerminalUI({ subscribe, height = '300px' }: TerminalUIProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const lastWasProgressRef = useRef<boolean>(false);

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm.js
    const term = new Terminal({
      theme: {
        background: '#1e1e1e',
        foreground: '#f3f3f3',
        cursor: '#f3f3f3',
        selectionBackground: 'rgba(255, 255, 255, 0.3)',
      },
      fontFamily: '"Fira Code", monospace, "Courier New", Courier',
      fontSize: 13,
      cursorBlink: true,
      disableStdin: true,
      convertEol: true, // Automagically convert \n to \r\n internally
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    term.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;

    term.writeln('\x1b[36mInitializing AI-Clipper Terminal...\x1b[0m');

    // Subscribe to websocket events
    const unsubscribe = subscribe((data: string) => {
      try {
        // Attempt to parse JSON to format it beautifully
        const parsed = JSON.parse(data.trim());
        let isProgress = false;
        let line = '';

        // Detect if this JSON represents a progress update
        const progressVal = parsed.progress ?? parsed.percent ?? parsed.p;
        if (progressVal !== undefined) {
           isProgress = true;
        }

        // 1. Map common status fields
        const status = parsed.status || parsed.step || parsed.task;
        if (status) {
           const statusStr = String(status).toUpperCase();
           const color = statusStr.includes('ERROR') || statusStr.includes('FAIL') ? '\x1b[31m' : '\x1b[36m';
           line += `${color}[${statusStr}]\x1b[0m `;
        }

        // 2. Draw progress bar if progress exists
        if (progressVal !== undefined) {
           const numProg = Number(progressVal);
           const barLength = 20;
           const filled = Math.round((numProg / 100) * barLength);
           const bar = '█'.repeat(Math.max(0, filled)) + '░'.repeat(Math.max(0, barLength - filled));
           line += `\x1b[32m${bar}\x1b[0m \x1b[33m${numProg.toFixed(1)}%\x1b[0m `;
        }

        // 3. Extract speed/eta
        const speed = parsed.speed || parsed.rate;
        if (speed) line += `| \x1b[35m⚡ ${speed}\x1b[0m `;

        const eta = parsed.eta || parsed.time_left;
        if (eta) line += `| \x1b[35m⏱ ETA: ${eta}\x1b[0m `;

        // 4. Extract detail messages
        const message = parsed.message || parsed.msg || parsed.detail || parsed.text;
        if (message) line += `| \x1b[37m${message}\x1b[0m`;

        // 5. Fallback for generic JSON without recognizable keys
        if (!status && progressVal === undefined && !message) {
           line += `\x1b[37m${JSON.stringify(parsed)}\x1b[0m`;
        }

        // Print logic based on whether we should overwrite the current line
        if (isProgress) {
           if (lastWasProgressRef.current) {
              // \r moves cursor to start of line, \x1b[2K clears the entire line
              term.write('\r\x1b[2K' + line);
           } else {
              // First progress entry, just write it
              term.write(line);
           }
           lastWasProgressRef.current = true;
        } else {
           if (lastWasProgressRef.current) {
              term.write('\r\n'); // End the previous progress line before printing new non-progress log
           }
           term.writeln(line); // writeln automatically appends a newline
           lastWasProgressRef.current = false;
        }

      } catch (e) {
        // Not a JSON string (e.g. SYSTEM logs or raw text from backend)
        if (lastWasProgressRef.current) {
           term.write('\r\n');
           lastWasProgressRef.current = false;
        }
        
        // Clean up Windows/Unix line endings dynamically since convertEol handles \n
        const formattedData = data.replace(/\r\r/g, '\r');
        term.write(formattedData);
      }
    });

    // Handle window resize
    const handleResize = () => {
      fitAddon.fit();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      unsubscribe();
      window.removeEventListener('resize', handleResize);
      term.dispose();
    };
  }, [subscribe]);

  return (
    <div className="terminal-container" style={{ height }}>
      <div className="terminal-header">
        <span className="terminal-title">System Pipeline Console</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
           <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#22c55e', boxShadow: '0 0 8px #22c55e' }}></div>
           <span style={{ fontSize: '10px', color: '#a0a0a0', fontFamily: 'monospace', fontWeight: 600, letterSpacing: '1px' }}>READY</span>
        </div>
      </div>
      <div className="terminal-body" ref={terminalRef}></div>
    </div>
  );
}
