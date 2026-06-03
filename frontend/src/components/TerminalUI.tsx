import { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { Box, Typography, LinearProgress, CircularProgress, useTheme } from '@mui/material';

interface TerminalUIProps {
  subscribe: (listener: (data: string) => void) => () => void;
  height?: string;
}

export function TerminalUI({ subscribe, height = '300px' }: TerminalUIProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const theme = useTheme();

  const [globalProgress, setGlobalProgress] = useState(0);
  const [globalStatus, setGlobalStatus] = useState('IDLE');
  const [globalIsRunning, setGlobalIsRunning] = useState(false);

  useEffect(() => {
    if (!terminalRef.current) return;

    const term = new Terminal({
      theme: {
        background: theme.palette.background.paper,
        foreground: theme.palette.text.primary,
        cursor: theme.palette.text.primary,
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

    term.writeln('\x1b[36mMemulai Terminal AI-Clipper...\x1b[0m');

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
        let currentStatusStr = globalStatus;
        if (parsed.status !== undefined && parsed.status !== null) {
          const s = String(parsed.status).toUpperCase();
          if (s !== '') {
            currentStatusStr = s;
            setGlobalStatus(s);
            setGlobalIsRunning(s === 'RUNNING' || s === 'PROCESSING');
          }
        }

        if (parsed.progress !== undefined) {
          const p = Number(parsed.progress);
          if (currentStatusStr.includes('SUCCESS') || currentStatusStr.includes('DONE')) {
            setGlobalProgress(100);
          } else {
            setGlobalProgress(p);
          }
        } else if (currentStatusStr.includes('SUCCESS') || currentStatusStr.includes('DONE')) {
          setGlobalProgress(100);
        }
        // --------------------------

        let baseText = '';
        const currentStep = parsed.step || '';
        const message = parsed.message || parsed.msg || parsed.detail || parsed.text || '';
        const status = parsed.status || parsed.step || parsed.task;

        if (message) {
          baseText = `\x1b[37m${message}\x1b[0m`;
        } else if (currentStep) {
          baseText = `\x1b[37m${currentStep}\x1b[0m`;
        }

        const isSuccess = String(parsed.status).toLowerCase() === 'success';
        const hasFiles = Array.isArray(parsed.output_files) && parsed.output_files.length > 0;

        // Handle final payload with output files directly
        if (isSuccess && hasFiles) {
          if (stateRef.step !== 'FINALIZED') {
            stateRef.isRunning = false;
            if (stateRef.step !== '' && stateRef.step !== 'FINALIZED') {
              term.write(`\r\x1b[2K\x1b[32m[✓]\x1b[0m ${stateRef.baseText}\r\n`);
            }
            term.write(`\r\x1b[2K\x1b[32m[✓]\x1b[0m \x1b[37mSemua proses berhasil diselesaikan.\x1b[0m\r\n`);
            stateRef.step = 'FINALIZED';
          }
          return;
        }

        // Handle completely raw JSON with no standard fields
        if (!status && parsed.progress === undefined && !message) {
          stateRef.isRunning = false;
          if (stateRef.step !== '' && stateRef.step !== 'FINALIZED') {
            term.write(`\r\x1b[2K\x1b[32m[✓]\x1b[0m ${stateRef.baseText}\r\n`);
            stateRef.step = '';
          }
          term.write(`\r\x1b[2K\x1b[37m${JSON.stringify(parsed)}\x1b[0m\r\n`);
          return;
        }

        const isRunning = status && String(status).toUpperCase().includes('RUNNING');
        const statusStr = String(status).toUpperCase();

        // If there is no step defined, treat as a standalone log
        if (!currentStep) {
          if (message) {
            if (stateRef.step !== '' && stateRef.step !== 'FINALIZED') {
              term.write(`\r\x1b[2K\x1b[32m[✓]\x1b[0m ${stateRef.baseText}\r\n`);
              stateRef.step = '';
            }

            if (statusStr.includes('ERROR') || statusStr.includes('FAIL')) {
              term.write(`\r\x1b[2K\x1b[31m[✗]\x1b[0m ${baseText}\r\n`);
            } else if (statusStr.includes('SUCCESS') || statusStr.includes('DONE')) {
              term.write(`\r\x1b[2K\x1b[32m[✓]\x1b[0m ${baseText}\r\n`);
            } else if (statusStr) {
              term.write(`\r\x1b[2K\x1b[36m[${statusStr}]\x1b[0m ${baseText}\r\n`);
            } else {
              term.write(`\r\x1b[2K${baseText}\r\n`);
            }
          }
          return;
        }

        const isNewStep = currentStep !== stateRef.step;

        stateRef.isRunning = false;

        if (isNewStep) {
          if (stateRef.step !== '' && stateRef.step !== 'FINALIZED') {
            // Finalize the previous step with a checkmark before moving to the next line
            term.write(`\r\x1b[2K\x1b[32m[✓]\x1b[0m ${stateRef.baseText}\r\n`);
          }
          stateRef.step = currentStep;
          stateRef.baseText = baseText;
        } else {
          // Update base text for the current step if it changed
          if (baseText) stateRef.baseText = baseText;
        }

        if (statusStr.includes('ERROR') || statusStr.includes('FAIL')) {
          term.write(`\r\x1b[2K\x1b[31m[✗]\x1b[0m ${stateRef.baseText}\r\n`);
          stateRef.step = ''; // Reset so next step starts fresh
        } else if (isRunning) {
          stateRef.isRunning = true;
          const spinner = spinnerFrames[Math.floor(Date.now() / 80) % spinnerFrames.length];
          term.write(`\r\x1b[2K\x1b[36m[${spinner}]\x1b[0m ${stateRef.baseText}`);
        } else if (statusStr.includes('SUCCESS') || statusStr.includes('DONE')) {
          // Write success on the current line, DO NOT append \r\n to prevent double prints.
          term.write(`\r\x1b[2K\x1b[32m[✓]\x1b[0m ${stateRef.baseText}`);
        } else if (statusStr) {
          term.write(`\r\x1b[2K\x1b[36m[${statusStr}]\x1b[0m ${stateRef.baseText}`);
        } else {
          term.write(`\r\x1b[2K${stateRef.baseText}`);
        }

      } catch (e) {
        // Not JSON = System message. Suspend animation, print cleanly.
        stateRef.isRunning = false;
        const formattedData = data.replace(/\r\n|\n|\r/g, '\r\n');

        if (stateRef.step !== '' && stateRef.step !== 'FINALIZED') {
          term.write(`\r\x1b[2K\x1b[32m[✓]\x1b[0m ${stateRef.baseText}\r\n`);
          stateRef.step = '';
        }
        term.write(`\r\x1b[2K${formattedData}\r\n`);
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
    <Box sx={{ display: 'flex', flexDirection: 'column', height, bgcolor: 'background.paper', borderRadius: 1, overflowX: 'hidden', overflowY: 'auto' }}>
      <Box sx={{
        bgcolor: 'rgba(0, 0, 0, 0.2)',
        px: 2,
        py: 1,
        borderBottom: 1,
        borderColor: 'divider',
        display: 'flex',
        alignItems: 'center',
        gap: 2
      }}>
        <Typography variant="overline" sx={{ color: 'text.secondary', fontWeight: 'bold', letterSpacing: 1, whiteSpace: 'nowrap' }}>
          Konsol Sistem
        </Typography>

        <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', gap: 2, bgcolor: 'background.default', px: 2, py: 0.5, borderRadius: 1, border: 1, borderColor: 'divider' }}>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace', minWidth: '100px' }}>
            {globalStatus} - {globalProgress.toFixed(1)}%
          </Typography>
          <Box sx={{ flex: 1 }}>
            <LinearProgress variant="determinate" value={globalProgress} color="success" sx={{ height: 6, borderRadius: 3, bgcolor: 'rgba(255,255,255,0.05)' }} />
          </Box>
        </Box>

        <Box sx={{ ml: 'auto', display: 'flex', gap: 1, alignItems: 'center' }}>
          {globalIsRunning && <CircularProgress size={14} thickness={5} />}
          <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: globalIsRunning ? 'warning.main' : 'success.main', boxShadow: `0 0 8px ${globalIsRunning ? theme.palette.warning.main : theme.palette.success.main}` }} />
          <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'monospace', fontWeight: 'bold', letterSpacing: 1 }}>
            {globalIsRunning ? 'BERJALAN' : 'SIAP'}
          </Typography>
        </Box>
      </Box>
      <Box sx={{ flex: 1, p: 1.5, overflow: 'hidden', '& .xterm': { height: '100%' } }} ref={terminalRef}></Box>
    </Box>
  );
}
