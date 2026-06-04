import { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { TerminalUI } from './components/TerminalUI';
import { Video } from 'lucide-react';
import { Plyr } from 'plyr-react';
import 'plyr/dist/plyr.css';
import './App.css';
import {
  Box,
  Typography,
  TextField,
  MenuItem,
  Button,
  Card,
  CardContent,
  CardActionArea,
  Chip,
  IconButton,
  Modal,
  Stack,
  Tooltip
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import CloseIcon from '@mui/icons-material/Close';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import DescriptionIcon from '@mui/icons-material/Description';

interface ClipResult {
  videoUrl: string;
  srtUrl: string;
  fileName: string;
  srtName: string;
  duration: string;
  videoTitle: string;
  topic: string;
  summary: string;
  aspectRatio: string;
  start: number;
  end: number;
}

function App() {
  const [wsUrl, setWsUrl] = useState<string | null>(null);
  const { subscribe, notifyListeners } = useWebSocket(wsUrl);

  const [url, setUrl] = useState('');
  const [ratio, setRatio] = useState('9:16');
  const [duration, setDuration] = useState('');
  const [count, setCount] = useState('');
  const [prompt, setPrompt] = useState('');
  const [timestamps, setTimestamps] = useState('');
  const [errors, setErrors] = useState<{ [k: string]: string }>({});
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState<ClipResult[]>([]);
  const [activeVideo, setActiveVideo] = useState<ClipResult | null>(null);
  const [sessionId, setSessionId] = useState<number>(0);
  const [terminalExpanded, setTerminalExpanded] = useState(true);

  useEffect(() => {
    const unsub = subscribe((data: string) => {
      try {
        const parsed = JSON.parse(data.trim());
        if (parsed.status === 'success' && parsed.output_files && parsed.output_files.length > 0) {
          setTerminalExpanded(false);
          const files: string[] = parsed.output_files;
          const videos = files.filter(f => f.endsWith('.mp4'));
          const srts = files.filter(f => f.endsWith('.srt'));
          const originalTitle = (parsed.video_path || '').split(/[/\\]/).pop()?.replace(/\.[^/.]+$/, "") || 'Video Klip';

          // Get clips metadata if available
          const clipsMetadata = parsed.clips_metadata || [];

          const paired = videos.map((vid, idx) => {
            const getMediaUrl = (pathStr: string) => {
              const parts = pathStr.replace(/\\/g, '/').split('/output/');
              if (parts.length > 1) {
                return `http://localhost:8000/media/${parts[1]}`;
              }
              return pathStr; // Fallback
            };

            const baseName = vid.replace('.mp4', '');
            const srt = srts.find(s => s.replace('.srt', '') === baseName);

            let durationStr = '-';
            const durMatch = vid.match(/_target_(\d+)s_/);
            if (durMatch) {
              durationStr = `${durMatch[1]}s`;
            } else {
              const tsMatch = vid.match(/timestamp_(\d+)s_to_(\d+)s/);
              if (tsMatch) {
                durationStr = `${parseInt(tsMatch[2]) - parseInt(tsMatch[1])}s`;
              }
            }

            // Get topic from metadata
            const metadata = clipsMetadata.find((m: any) => m.index === idx);
            const topic = metadata?.topic || 'Video Clip';
            const summary = metadata?.summary || '';
            const aspectRatio = metadata?.aspect_ratio || '9:16';
            const start = metadata?.start ?? 0;
            const end = metadata?.end ?? 0;

            return {
              videoUrl: getMediaUrl(vid),
              srtUrl: srt ? getMediaUrl(srt) : '',
              fileName: vid.split('/').pop()?.split('\\').pop() || 'video.mp4',
              srtName: srt ? (srt.split('/').pop()?.split('\\').pop() || '') : '',
              duration: durationStr,
              videoTitle: originalTitle,
              topic: topic,
              summary: summary,
              aspectRatio: aspectRatio,
              start,
              end
            };
          });
          setResults(paired);
        }
      } catch (e) {
        // Not a JSON or other error, ignore
      }
    });
    return unsub;
  }, [subscribe]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // client-side validation
    const ok = validateForm();
    if (!ok) return;

    setIsProcessing(true);
    setResults([]);
    setTerminalExpanded(true);
    setSessionId(prev => prev + 1); // Reset terminal UI by unmounting/remounting

    try {
      const response = await fetch('http://localhost:8000/api/v1/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url,
          aspect_ratio: ratio,
          target_duration: duration ? parseInt(duration, 10) : undefined,
          output_count: count ? parseInt(count, 10) : undefined,
          prompt_context: prompt || undefined,
          custom_timestamps: timestamps || undefined
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      if (data.job_id) {
        setWsUrl(`ws://localhost:8000/api/v1/ws/status/${data.job_id}`);
      } else {
        notifyListeners(JSON.stringify({ status: 'ERROR', message: 'Unexpected response: No job_id returned', step: 'error' }));
      }
    } catch (error) {
      notifyListeners(JSON.stringify({ status: 'ERROR', message: `Failed to start processing: ${error instanceof Error ? error.message : String(error)}`, step: 'error' }));
    } finally {
      setIsProcessing(false);
    }
  };

  const validateTimestamps = (val: string) => {
    if (!val) return true;
    // Accept formats like MM:SS-MM:SS or HH:MM:SS-HH:MM:SS, comma separated
    const rangeRe = /^(\d{1,2}:\d{2}(?::\d{2})?)-(\d{1,2}:\d{2}(?::\d{2})?)(\s*,\s*\d{1,2}:\d{2}(?::\d{2})?-\d{1,2}:\d{2}(?::\d{2})?)*$/;
    return rangeRe.test(val.trim());
  };

  const validateForm = () => {
    const newErr: { [k: string]: string } = {};
    if (!url || url.trim() === '') {
      newErr.url = 'URL video wajib diisi.';
    }
    if (duration) {
      const d = parseInt(duration, 10);
      if (isNaN(d) || d <= 0) newErr.duration = 'Durasi harus angka positif.';
    }
    if (count) {
      const c = parseInt(count, 10);
      if (isNaN(c) || c <= 0) newErr.count = 'Jumlah keluaran harus angka positif.';
    }
    if (!validateTimestamps(timestamps)) {
      newErr.timestamps = 'Format timestamp tidak valid. Contoh: 01:20-02:00, 05:00-06:30';
    }

    setErrors(newErr);
    return Object.keys(newErr).length === 0;
  };

  const formatClipTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, height: '100vh', width: '100vw', overflow: 'hidden', bgcolor: 'background.default', color: 'text.primary' }}>
      {/* Left Panel: Input Form */}
      <Box component="aside" sx={{ width: { xs: '100%', md: '400px' }, flexShrink: 0, p: 3, borderRight: 1, borderColor: 'divider', overflowY: 'auto', bgcolor: 'background.paper', display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Video color="#2563eb" size={32} />
          <Typography variant="h5" component="h1" sx={{ fontWeight: 'bold' }}>
            AI Clipper
          </Typography>
        </Box>

        <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          <TextField
            label="URL YouTube"
            type="url"
            required
            placeholder="https://www.youtube.com/watch?v=..."
            value={url}
            onChange={(e) => { const v = e.target.value; setUrl(v); if (v && v.trim() !== '') setErrors(prev => { const p = { ...prev }; delete p.url; return p; }); }}
            onBlur={() => { if (!url) setErrors(prev => ({ ...prev, url: 'URL video wajib diisi.' })); else setErrors(prev => { const p = { ...prev }; delete p.url; return p; }) }}
            error={!!errors.url}
            helperText={errors.url || "Masukkan URL YouTube yang valid."}
            disabled={isProcessing}
            fullWidth
            size="small"
          />

          <Stack direction="row" spacing={2}>
            <TextField
              select
              label="Rasio Aspek"
              value={ratio}
              onChange={(e) => setRatio(e.target.value)}
              disabled={isProcessing}
              fullWidth
              size="small"
            >
              <MenuItem value="9:16">Vertikal (9:16)</MenuItem>
              <MenuItem value="16:9">Horizontal (16:9)</MenuItem>
            </TextField>

            <TextField
              label="Durasi Target (dtk)"
              type="text"
              placeholder="mis. 60"
              value={duration}
              onChange={(e) => { const raw = e.target.value; const sanitized = raw.replace(/\D/g, ''); setDuration(sanitized); if (sanitized && !isNaN(parseInt(sanitized, 10)) && parseInt(sanitized, 10) > 0) setErrors(prev => { const p = { ...prev }; delete p.duration; return p; }); }}
              onBlur={() => { if (duration && (isNaN(parseInt(duration, 10)) || parseInt(duration, 10) <= 0)) setErrors(prev => ({ ...prev, duration: 'Harus angka positif.' })); else setErrors(prev => { const p = { ...prev }; delete p.duration; return p; }) }}
              error={!!errors.duration}
              helperText={errors.duration}
              disabled={isProcessing}
              fullWidth
              size="small"
            />
          </Stack>

          <TextField
            label="Maks Jumlah Klip"
            type="text"
            placeholder="mis. 5"
            value={count}
            onChange={(e) => { const raw = e.target.value; const sanitized = raw.replace(/\D/g, ''); setCount(sanitized); if (sanitized && !isNaN(parseInt(sanitized, 10)) && parseInt(sanitized, 10) > 0) setErrors(prev => { const p = { ...prev }; delete p.count; return p; }); }}
            onBlur={() => { if (count && (isNaN(parseInt(count, 10)) || parseInt(count, 10) <= 0)) setErrors(prev => ({ ...prev, count: 'Harus angka positif.' })); else setErrors(prev => { const p = { ...prev }; delete p.count; return p; }) }}
            error={!!errors.count}
            helperText={errors.count}
            disabled={isProcessing}
            fullWidth
            size="small"
          />

          <TextField
            label="Konteks AI (opsional)"
            multiline
            rows={3}
            placeholder="Contoh: Cari momen emosional, puncak narasi..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={isProcessing}
            fullWidth
            size="small"
          />

          <TextField
            label="Timestamp Kustom (opsional)"
            type="text"
            placeholder="mis. 01:20-02:00, 05:00-06:30"
            value={timestamps}
            onChange={(e) => { const v = e.target.value; setTimestamps(v); if (validateTimestamps(v)) setErrors(prev => { const p = { ...prev }; delete p.timestamps; return p; }); }}
            onBlur={() => { if (timestamps && !validateTimestamps(timestamps)) setErrors(prev => ({ ...prev, timestamps: 'Format tidak valid.' })); else setErrors(prev => { const p = { ...prev }; delete p.timestamps; return p; }) }}
            error={!!errors.timestamps}
            helperText={errors.timestamps || "Format: MM:SS-MM:SS. Pisahkan dgn koma."}
            disabled={isProcessing}
            fullWidth
            size="small"
          />

          <Button
            type="submit"
            variant="contained"
            color="primary"
            size="large"
            disabled={isProcessing}
            startIcon={<PlayArrowIcon />}
            sx={{ mt: 1, py: 1.5, fontWeight: 'bold' }}
          >
            {isProcessing ? 'Mengirim...' : 'Mulai Proses'}
          </Button>
        </Box>
      </Box>

      {/* Right Panel: Terminal Pipeline and Results */}
      <Box component="main" sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>

        <Box sx={{ 
          height: terminalExpanded ? { xs: '30vh', md: '30%' } : 'auto', 
          flexShrink: 0, 
          borderBottom: 1, 
          borderColor: 'divider', 
          overflow: 'hidden',
          transition: 'height 0.3s ease-in-out'
        }}>
          <TerminalUI 
            key={`term-${sessionId}`} 
            subscribe={subscribe} 
            height={terminalExpanded ? "100%" : "auto"} 
            isExpanded={terminalExpanded}
            onToggle={() => setTerminalExpanded(!terminalExpanded)}
          />
        </Box>

        <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#121212', overflow: 'hidden' }}>
          <Box sx={{ p: 3, pb: 2, borderBottom: 1, borderColor: 'rgba(255,255,255,0.05)' }}>
            <Typography variant="h5" component="h2" sx={{ fontWeight: 'bold' }}>
              Hasil Kliping
            </Typography>
          </Box>

          <Box sx={{ flexGrow: 1, overflowY: 'auto', p: 3 }}>
            {results.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 8, color: 'text.secondary' }}>
                <Typography variant="body1">Belum ada hasil kliping video. Silakan kirim proses baru.</Typography>
              </Box>
            ) : (
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 3 }}>
                {results.map((res, idx) => (
                  <Card
                    key={idx}
                    sx={{
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      transition: 'transform 0.2s',
                      '&:hover': { transform: 'translateY(-4px)', boxShadow: 6 }
                    }}
                  >
                    <CardActionArea onClick={() => setActiveVideo(res)} sx={{ position: 'relative' }}>
                      <Box sx={{ position: 'relative', paddingTop: res.aspectRatio === '16:9' ? '56.25%' : '177.78%', bgcolor: 'black' }}>
                        <video
                          src={res.videoUrl}
                          preload="metadata"
                          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'contain' }}
                        />
                        <Box sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', bgcolor: 'rgba(0,0,0,0.5)', borderRadius: '50%', p: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <PlayArrowIcon sx={{ fontSize: 48, color: 'white' }} />
                        </Box>
                        <Chip
                          label={`Klip #${idx + 1}`}
                          color="primary"
                          size="small"
                          sx={{ position: 'absolute', top: 8, left: 8, fontWeight: 'bold' }}
                        />
                      </Box>
                    </CardActionArea>
                    <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Typography variant="subtitle1" component="h3" sx={{
                        fontWeight: 'bold',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        lineHeight: 1.2,
                        mb: 1
                      }}>
                        {res.topic}
                      </Typography>

                      {res.summary && (
                        <Typography variant="body2" color="text.secondary" sx={{
                          display: '-webkit-box',
                          WebkitLineClamp: 3,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                          mb: 1
                        }}>
                          {res.summary}
                        </Typography>
                      )}

                      <Stack direction="row" spacing={2} sx={{ mt: 'auto', flexWrap: 'wrap', gap: 1 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
                          <AccessTimeIcon fontSize="small" />
                          <Typography variant="body2"><strong>Durasi:</strong> {res.duration}</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
                          <Typography variant="body2"><strong>Range:</strong> {formatClipTime(res.start)} - {formatClipTime(res.end)}</Typography>
                        </Box>
                      </Stack>
                      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                        <Chip label={`Rasio ${res.aspectRatio}`} size="small" variant="outlined" />
                        {res.srtName && (
                          <Tooltip title={res.srtName} arrow placement="top">
                            <Chip icon={<DescriptionIcon fontSize="small" />} label="Subtitle" size="small" color="secondary" variant="outlined" sx={{ cursor: 'pointer' }} />
                          </Tooltip>
                        )}
                      </Stack>
                    </CardContent>
                  </Card>
                ))}
              </Box>
            )}
          </Box>
        </Box>
      </Box>

      {/* Video Modal Overlay */}
      <Modal
        open={!!activeVideo}
        onClose={() => setActiveVideo(null)}
        sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}
      >
        <Box sx={{ position: 'relative', width: '100%', maxWidth: ratio === '16:9' ? '1000px' : '450px', bgcolor: 'black', borderRadius: 2, overflow: 'hidden', outline: 'none', boxShadow: 24 }}>
          <IconButton
            onClick={() => setActiveVideo(null)}
            sx={{ position: 'absolute', top: 8, right: 8, color: 'white', zIndex: 10, bgcolor: 'rgba(0,0,0,0.5)', '&:hover': { bgcolor: 'rgba(0,0,0,0.7)' } }}
          >
            <CloseIcon />
          </IconButton>
          {activeVideo && (
            <Box sx={{ width: '100%', aspectRatio: ratio.replace(':', '/') }}>
              <Plyr
                source={{
                  type: 'video',
                  sources: [{ src: activeVideo.videoUrl, type: 'video/mp4' }]
                }}
                options={{
                  autoplay: true,
                  controls: ['play-large', 'play', 'progress', 'current-time', 'mute', 'volume', 'fullscreen'],
                }}
              />
            </Box>
          )}
        </Box>
      </Modal>
    </Box>
  );
}

export default App;
