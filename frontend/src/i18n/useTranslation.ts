import { useLang } from './LangContext';

export function useTranslation() {
  const { t, lang, setLang } = useLang();
  return { t, lang, setLang };
}

export default useTranslation;
