from __future__ import annotations

import functools
import re
from typing import Dict, List, Optional, Tuple

import requests


NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _normalize_image(image: str) -> Tuple[str, Optional[str]]:
    """
    Normalize a Docker image reference into:
      - repository/image name
      - version/tag prefix suitable for rough matching
    """
    repo = image.split("/")[-1]
    repo = repo.split("@")[0]

    if ":" in repo:
        name, tag = repo.split(":", 1)
    else:
        name, tag = repo, None

    version = None
    if tag:
        m = re.match(r"(\d+(?:\.\d+){0,2})", tag)
        if m:
            version = m.group(1)

    return name.lower(), version


def _build_search_terms_for_product(name: str) -> List[str]:
    mapping = {
        "python": ["python"],
        "node": ["node.js", "nodejs", "node"],
        "nginx": ["nginx"],
        "alpine": ["alpine linux", "alpine"],
        "ubuntu": ["ubuntu"],
        "debian": ["debian"],
        "redis": ["redis"],
        "postgres": ["postgresql", "postgres"],
        "mysql": ["mysql"],
        "mariadb": ["mariadb"],
        "httpd": ["apache http server", "httpd", "apache"],
        "openjdk": ["openjdk", "jdk", "java"],
        "jenkins": ["jenkins"],
        "gitlab": ["gitlab"],
    }
    return mapping.get(name, [name])


def _cve_text(vuln: dict) -> str:
    cve = vuln.get("cve", {})
    parts = [cve.get("id", "")]

    for desc in cve.get("descriptions", []):
        value = desc.get("value")
        if value:
            parts.append(value)

    for ref in cve.get("references", []):
        url = ref.get("url")
        if url:
            parts.append(url)

    for config in cve.get("configurations", []):
        parts.append(str(config))

    return " ".join(parts).lower()


def _cve_matches_product(vuln: dict, product_terms: List[str], version: Optional[str]) -> bool:
    text = _cve_text(vuln)

    if not any(term.lower() in text for term in product_terms):
        return False

    if version:
        if version not in text:
            major_minor = ".".join(version.split(".")[:2])
            if major_minor not in text:
                major = version.split(".")[0]
                if major not in text:
                    return False
    return True

@functools.lru_cache(maxsize=256)
def _search_cves(keyword: str) -> List[dict]:
    params = {
        "keywordSearch": keyword,
        "resultsPerPage": 50, # Increased to get more results
    }

    try:
        resp = requests.get(NVD_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        return body.get("vulnerabilities", [])
    except Exception:
        return []

def lookup_product_cves(product: str, version: str, max_cves: int = 5) -> List[Dict[str, str]]:
    if not version:
        return []

    product_terms = _build_search_terms_for_product(product)
    keyword = product_terms[0]
    
    vulns = _search_cves(keyword)

    cves: List[Dict[str, str]] = []
    seen = set()

    for vuln in vulns:
        if not _cve_matches_product(vuln, product_terms, version):
            continue

        cve = vuln.get("cve", {})
        cve_id = cve.get("id")
        if not cve_id or cve_id in seen:
            continue

        seen.add(cve_id)
        cves.append(
            {
                "id": cve_id,
                "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
            }
        )

        if len(cves) >= max_cves:
            break
            
    return cves


@functools.lru_cache(maxsize=256)
def lookup_image_cves(image: str) -> List[Dict[str, str]]:
    """
    Heuristic CVE lookup for Docker base images.
    """
    name, version = _normalize_image(image)

    if not version:
        return []
        
    return lookup_product_cves(name, version)