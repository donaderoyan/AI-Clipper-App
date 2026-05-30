import { useEffect, useRef, useState } from 'react';
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

  const [globalProgress, setGlobalProgress] = useState(0);
  const [globalStatus, setGlobalStatus] = useState('IDLE');
  const [globalIsRunning, setGlobalIsRunning] = useState(false);

  useEffect(() => {
    if (!terminalRef.current) return;

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
      convertEol: true, 
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    term.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;

    term.writeln('\x1b[36mInitializing AI-Clipper Terminal...\x1b[0m');

    const spinnerFrames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
    
    // State to drive the continuous animation
    const stateRef = { 
       step: '', 
       baseText: '', 
       isRunning: false 
    };

    // Continuous render loop for the spinner
    const intervalId = setInterval(() => {
        if (stateRef.isRunning) {
            const spinner = spinnerFrames[Math.floor(Date.now() / 80) % spinnerFrames.length];
            term.write(`\r\x1b[2K\x1b[36m[${spinner}]\x1b[0m ${stateRef.baseText}`);
        }
    }, 100);

    const unsubscribe = subscribe((data: string) => {
      try {
        const parsed = JSON.parse(data.trim());
        
        // --- GLOBAL STATE LOGIC ---
        if (parsed.progress !== undefined) {
          setGlobalProgress(Number(parsed.progress));
        }
        if (parsed.status) {
          const s = String(parsed.status).toUpperCase();
          setGlobalStatus(s);
          setGlobalIsRunning(s === 'RUNNING');
        }
        // --------------------------

        let baseText = '';
        
        const currentStep = parsed.step || '';
        const message = parsed.message || parsed.msg || parsed.detail || parsed.text || '';
        const progressVal = parsed.progress ?? parsed.percent ?? parsed.p;
        const status = parsed.status || parsed.step || parsed.task;

        const isRunning = status && String(status).toUpperCase().includes('RUNNING');
        
        if (message) {
            baseText += `\x1b[37m${message}\x1b[0m `;
        }
        if (!status && progressVal === undefined && !message) {
           baseText += `\x1b[37m${JSON.stringify(parsed)}\x1b[0m`;
        }

        const isNewStep = currentStep && currentStep !== stateRef.step;

        // Briefly stop spinner so we can safely draw new lines if needed
        stateRef.isRunning = false;

        if (isNewStep) {
            if (stateRef.step !== '') {
                // Finalize the previous step with a checkmark before moving to the next line
                term.write(`\r\x1b[2K\x1b[32m[✓]\x1b[0m ${stateRef.baseText}\r\n`);
            }
            stateRef.step = currentStep;
        }

        if (!isRunning) {
           let statusLine = '';
           const statusStr = String(status).toUpperCase();
           if (statusStr.includes('SUCCESS') || statusStr.includes('DONE')) {
               statusLine = `\x1b[32m[✓]\x1b[0m ${baseText}`;
           } else if (statusStr.includes('ERROR') || statusStr.includes('FAIL')) {
               statusLine = `\x1b[31m[✗]\x1b[0m ${baseText}`;
           } else if (statusStr) {
               statusLine = `\x1b[36m[${statusStr}]\x1b[0m ${baseText}`;
           } else {
               statusLine = baseText;
           }
           term.write(`\r\x1b[2K${statusLine}`);
           if (statusStr.includes('SUCCESS') || statusStr.includes('ERROR') || statusStr.includes('FAIL')) {
               term.write('\r\n');
               stateRef.step = ''; // Reset so we don't finalize it again if a new job starts
           }
        } else {
           // Initial draw before interval catches up
           const spinner = spinnerFrames[Math.floor(Date.now() / 80) % spinnerFrames.length];
           term.write(`\r\x1b[2K\x1b[36m[${spinner}]\x1b[0m ${baseText}`);
           
           // Resume spinner
           stateRef.isRunning = true;
           stateRef.baseText = baseText;
        }

      } catch (e) {
        // Not JSON = System message. Suspend animation, print cleanly, reset step.
        stateRef.isRunning = false; 
        const formattedData = data.replace(/\r\n|\n|\r/g, '\r\n');
        
        if (stateRef.step !== '') {
            // Finalize previous step if system message interrupts
            term.write(`\r\x1b[2K\x1b[32m[✓]\x1b[0m ${stateRef.baseText}\r\n`);
            stateRef.step = '';
        }
        term.write(`\r\x1b[2K${formattedData}`);
      }
    });

    const handleResize = () => {
      fitAddon.fit();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      clearInterval(intervalId);
      unsubscribe();
      window.removeEventListener('resize', handleResize);
      term.dispose();
    };
  }, [subscribe]);

  return (
    <div className="terminal-container" style={{ height }}>
      <div className="terminal-header">
        <span className="terminal-title">System Pipeline Console</span>
        
        <div className="terminal-global-progress">
           <div className="progress-info">
              <span>{globalStatus}</span>
              <span>{globalProgress.toFixed(1)}%</span>
           </div>
           <div className="progress-bar-bg">
              <div className="progress-bar-fill" style={{ width: `${globalProgress}%` }}></div>
           </div>
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
           {globalIsRunning && <div className="header-spinner"></div>}
           <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: globalIsRunning ? '#f59e0b' : '#22c55e', boxShadow: `0 0 8px ${globalIsRunning ? '#f59e0b' : '#22c55e'}` }}></div>
           <span style={{ fontSize: '10px', color: '#a0a0a0', fontFamily: 'monospace', fontWeight: 600, letterSpacing: '1px' }}>
              {globalIsRunning ? 'RUNNING' : 'READY'}
           </span>
        </div>
      </div>
      <div className="terminal-body" ref={terminalRef}></div>
    </div>
  );
}
