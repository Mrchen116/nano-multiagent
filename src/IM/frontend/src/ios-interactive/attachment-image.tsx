import { useEffect, useState } from 'react';
import { ImageIcon } from 'lucide-react';
import { AttachmentPreviewTrigger } from '../features/chat/interactive/open-intelligent-ui/attachment-images';
import { nativeRequest } from './bridge';

export function NativeAttachmentImage({index, alt, onVisibility}: {
  index: number;
  alt: string;
  onVisibility(index: number, visible: boolean): void;
}) {
  const [url, setUrl] = useState<string | null>();
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl: string | undefined;
    void nativeRequest({type: 'attachment-image', index}).then(value => {
      if (!active) return;
      const image = value as {data: string; mime: string};
      if (!/^image\/(?:png|jpeg|gif|webp)$/.test(image.mime)) throw new Error('Unsupported attachment image');
      const bytes = Uint8Array.from(atob(image.data), character => character.charCodeAt(0));
      objectUrl = URL.createObjectURL(new Blob([bytes], {type: image.mime}));
      setUrl(objectUrl);
    }).catch(() => { if (active) setUrl(null); });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [index]);

  useEffect(() => {
    if (!url || !loaded) return;
    onVisibility(index, true);
    return () => onVisibility(index, false);
  }, [index, loaded, onVisibility, url]);

  if (url === undefined) return null;
  if (url === null) return <ImageIcon className="iui-image-empty" role="img" aria-label={alt} />;
  return <AttachmentPreviewTrigger aria-label={alt}
    onActivate={() => { if (loaded) void nativeRequest({type: 'attachment-open', index}).catch(() => setUrl(null)); }}>
    <img src={url} alt={alt} onLoad={() => setLoaded(true)} onError={() => setUrl(null)} />
  </AttachmentPreviewTrigger>;
}
