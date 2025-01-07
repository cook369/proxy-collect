const cheerio = require('cheerio');
const fs = require('fs');
const axios = require('axios');
const CryptoJS = require('crypto-js');
const path = require('path');

const HOME_URL = 'https://www.yudou66.com/';
const OUTPUT_DIR = path.resolve(__dirname, '../output');

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

async function fetchHtml(url) {
  try {
    const response = await axios.get(url);
    return cheerio.load(response.data);
  } catch (error) {
    console.error(`Failed to fetch URL: ${url}`, error);
    throw error;
  }
}

function extractEncryptionScript($) {
  let encryption = '';
  $('script:not([src])').each((index, element) => {
    const scriptData = $(element).html();
    const match = scriptData && scriptData.match(/encryption = \[.*?\]/s);
    if (match) {
      encryption = match[0].split('"')[1];
      return false;
    }
  });
  return encryption;
}

function bruteForceDecrypt(encryption) {
  for (let password = 1000; password < 10000; password++) {
    try {
      const decrypted = CryptoJS.AES.decrypt(encryption, password.toString()).toString(CryptoJS.enc.Utf8);
      
      if (decrypted) {
        console.info(`Password found: ${password}`);
        return decodeURIComponent(decrypted);
      }
    } catch (error) {
      // Continue trying next password
    }
  }
  throw new Error('Failed to decrypt the encryption data');
}

function parseUrlsFromData() {
  const urls = data.match(/http.*\.(txt|yaml)/g);
  if (urls.length === 0) {
    throw new Error('No URLs found in decrypted data');
  }
  return urls;
}

async function downloadAndSaveFiles(urls) {
  for (const url of urls) {
    try {
      console.info(`Downloading from ${url}`);
      const response = await axios.get(url);
      let outputFile = '';

      if (url.endsWith('.txt')) {
        outputFile = path.join(OUTPUT_DIR, 'v2ray.txt');
      } else if (url.endsWith('.yaml')) {
        outputFile = path.join(OUTPUT_DIR, 'clash.yaml');
      }

      if (outputFile) {
        fs.writeFileSync(outputFile, response.data, 'utf8');
        console.info(`Saved file: ${outputFile}`);
      }
    } catch (error) {
      console.error(`Failed to download or save file from URL: ${url}`, error);
    }
  }
}

async function scrapeData() {
  try {
    // Step 1: Fetch homepage and extract the first link
    const $home = await fetchHtml(HOME_URL);
    const articleLink = $home('#main article:first-child div.entry-header a').attr('href');
    if (!articleLink) throw new Error('Failed to find article link on homepage');
    console.info(`Found article link: ${articleLink}`);

    // Step 2: Fetch article page and extract encryption data
    const $article = await fetchHtml(articleLink);
    const encryption = extractEncryptionScript($article);
    if (!encryption) throw new Error('Failed to extract encryption data');
    console.info('Encryption data extracted successfully');

    // Step 3: Decrypt the data
    const decryptedData = bruteForceDecrypt(encryption);
    console.info('Decryption successful');

    // Step 4: Parse URLs from decrypted data
    const urls = parseUrlsFromData(decryptedData);
    console.info('URLs parsed successfully:', urls);

    // Step 5: Download and save files
    await downloadAndSaveFiles(urls);
    console.info('All files downloaded successfully');

  } catch (error) {
    console.error('An error occurred:', error);
  }
}

scrapeData();
