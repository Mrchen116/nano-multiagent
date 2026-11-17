import { useTranslation } from '../../../i18n';
import { AssistantPortrait } from './assistant-portrait';
import './avatar-picker.css';

/** Choose a preset without making appearance a required setup step. */
export function AvatarPicker({ personal = false, value, onChange, disabled = false }: {
  personal?: boolean; value: number; onChange(value: number): void; disabled?: boolean;
}) {
  const { t } = useTranslation();
  const color = value % 6, style = Math.floor(value / 6);
  return <fieldset className="avatar-picker" disabled={disabled}>
    <legend>{t('avatarPicker.title')}</legend>
    <div className="avatar-picker-layout">
      <div className="avatar-picker-preview"><AssistantPortrait personal={personal} variant={value} size={88} /></div>
      <div className="avatar-picker-controls">
        <div className="avatar-picker-styles" role="group" aria-label={t('avatarPicker.style')}>
          {[0, 1, 2, 3].map(index => <button key={index} type="button" aria-pressed={style === index}
            aria-label={t(`avatarPicker.${personal ? 'personal' : 'agent'}.${index}`)}
            onClick={() => onChange(index * 6 + color)}><AssistantPortrait personal={personal} variant={index * 6 + color} size={40} /></button>)}
        </div>
        <div className="avatar-picker-colors" role="group" aria-label={t('avatarPicker.color')}>
          {['#b9a2df', '#79af98', '#85a8d6', '#e8a385', '#d991b6', '#d9be6f'].map((swatch, index) => <button key={swatch} type="button" aria-pressed={color === index}
            aria-label={t(`avatarPicker.colors.${index}`)} onClick={() => onChange(style * 6 + index)}><span style={{background:swatch}} /></button>)}
        </div>
      </div>
    </div>
  </fieldset>;
}
