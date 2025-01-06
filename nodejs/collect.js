const cheerio = require('cheerio');
const fs = require('fs');
const axios = require('axios');
const CryptoJS = require('crypto-js');

const homeUrl = 'https://www.yudou66.com/';

async function scrapeData() {
  const response = await axios.get(homeUrl);
  let $ = cheerio.load(response.data);

  const link = $('#main article:first-child div.entry-header a').attr('href');

  const response2 = await axios.get(link);
  $ = cheerio.load(response2.data);

  let encryption = '';
  $('script:not([src])').each((index, element) => {
    let script_data = $(element).get()[0].children[0].data;
    let match = script_data.match(/encryption = (\[.*?\])/s);
    if (match == null) {
      return;
    }
    encryption = match[1].split('"')[1];
  });
  console.log(encryption);

  let data = '';

  for (let i = 1000; i < 10000; i++) {
    try {
      data = CryptoJS.AES.decrypt(encryption, i.toString()).toString(
        CryptoJS.enc.Utf8,
      );
      break;
    } catch (e) {}
  }

  if (data == '') {
    return;
  }
  let resp_data = decodeURIComponent(data);
  $ = cheerio.load(resp_data);

  let urls = [];

  $('br').each((index, element) => {
    let data = $(element).get()[0].next.data;
    if (data != undefined && data.substring(0, 4) === 'http') {
      urls.push(data);
    }
  });
  console.log(urls);

  urls.forEach(async (url, inedx) => {
    const response = await axios.get(url);
    if (url.substring(url.length - 3, url.length) === 'txt') {
      fs.writeFileSync('../output/v2rat.txt', response.data);
    } else if (url.substring(url.length - 4, url.length) === 'yaml') {
      fs.writeFileSync('../output/clash.yaml', response.data);
    }
  });
}

scrapeData();
