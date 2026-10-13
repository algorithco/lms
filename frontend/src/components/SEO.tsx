import { useEffect } from 'react';

export interface SEOProps {
  title?: string;
  description?: string;
  keywords?: string;
  canonical?: string;
  image?: string;
  type?: 'website' | 'article' | 'profile';
  robots?: string;
  jsonLd?: Record<string, unknown> | Array<Record<string, unknown>>;
}

const DEFAULT_TITLE = 'GRANDEC — Ona tili va adabiyot LMS | Milliy sertifikat & AI Esse';
const DEFAULT_DESC =
  "Ona tili va adabiyoti bo'yicha Milliy sertifikatga tayyorlovchi zamonaviy LMS platformasi va AI Esse tahlil tizimi. 1v1 Arena duellari, testlar banki va rasmiy BMB mezonlari.";
const DEFAULT_IMAGE = 'https://grandec.uz/grandec.png';
const SITE_URL = 'https://grandec.uz';

function setMetaTag(selector: string, attrName: string, attrValue: string, content: string) {
  let element = document.querySelector<HTMLMetaElement>(selector);
  if (!element) {
    element = document.createElement('meta');
    element.setAttribute(attrName, attrValue);
    document.head.appendChild(element);
  }
  element.setAttribute('content', content);
}

function setLinkTag(rel: string, href: string) {
  let element = document.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!element) {
    element = document.createElement('link');
    element.setAttribute('rel', rel);
    document.head.appendChild(element);
  }
  element.setAttribute('href', href);
}

export default function SEO({
  title,
  description = DEFAULT_DESC,
  keywords = 'ona tili, milliy sertifikat, esse, insho, bmb, adabiyot, test, ai esse, 1v1 arena, grand education',
  canonical,
  image = DEFAULT_IMAGE,
  type = 'website',
  robots = 'index, follow',
  jsonLd,
}: SEOProps) {
  useEffect(() => {
    // Document Title
    const formattedTitle = title ? `${title} | GRANDEC` : DEFAULT_TITLE;
    document.title = formattedTitle;

    // Standard Meta Tags
    setMetaTag('meta[name="description"]', 'name', 'description', description);
    setMetaTag('meta[name="keywords"]', 'name', 'keywords', keywords);
    setMetaTag('meta[name="robots"]', 'name', 'robots', robots);

    // Canonical URL
    const canonicalUrl = canonical ? `${SITE_URL}${canonical}` : window.location.href;
    setLinkTag('canonical', canonicalUrl);

    // OpenGraph
    setMetaTag('meta[property="og:title"]', 'property', 'og:title', formattedTitle);
    setMetaTag('meta[property="og:description"]', 'property', 'og:description', description);
    setMetaTag('meta[property="og:type"]', 'property', 'og:type', type);
    setMetaTag('meta[property="og:url"]', 'property', 'og:url', canonicalUrl);
    setMetaTag('meta[property="og:image"]', 'property', 'og:image', image);
    setMetaTag('meta[property="og:site_name"]', 'property', 'og:site_name', 'GRANDEC LMS');
    setMetaTag('meta[property="og:locale"]', 'property', 'og:locale', 'uz_UZ');

    // Twitter Card
    setMetaTag('meta[name="twitter:card"]', 'name', 'twitter:card', 'summary_large_image');
    setMetaTag('meta[name="twitter:title"]', 'name', 'twitter:title', formattedTitle);
    setMetaTag('meta[name="twitter:description"]', 'name', 'twitter:description', description);
    setMetaTag('meta[name="twitter:image"]', 'name', 'twitter:image', image);

    // JSON-LD Scripts
    const scriptId = 'seo-json-ld';
    let scriptEl = document.getElementById(scriptId) as HTMLScriptElement | null;
    if (jsonLd) {
      if (!scriptEl) {
        scriptEl = document.createElement('script');
        scriptEl.id = scriptId;
        scriptEl.type = 'application/ld+json';
        document.head.appendChild(scriptEl);
      }
      scriptEl.textContent = JSON.stringify(jsonLd);
    } else if (scriptEl) {
      scriptEl.remove();
    }

    return () => {
      // Optional cleanup if needed
    };
  }, [title, description, keywords, canonical, image, type, robots, jsonLd]);

  return null;
}
