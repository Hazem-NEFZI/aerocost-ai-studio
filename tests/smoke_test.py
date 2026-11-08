"""Headless browser tests for the dependency-free AEROCOST AI 2.0 UI."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / 'AEROCOST_AI_2_Offline_Demo.html').read_text(encoding='utf-8')


def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1500, 'height': 930}, accept_downloads=True)
        errors=[]
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content(html, wait_until='load')
        assert 'AEROCOST' in page.title()
        assert 'defensible quotation' in page.locator('h1').inner_text()
        page.get_by_role('button', name='3D Quote Studio').first.click()
        assert page.locator('canvas#partCanvas').count() == 1
        assert page.locator('.kpi').count() == 4
        original=page.locator('.kpi .number').first.inner_text()
        page.locator('#v-batch').fill('48')
        page.locator('#v-batch').dispatch_event('change')
        assert page.locator('#v-batch').input_value()=='48'
        updated=page.locator('.kpi .number').first.inner_text()
        assert original!=updated,(original,updated)
        with page.expect_download() as dl:
            page.locator('#sampleSTL').click()
        sample=dl.value
        assert sample.suggested_filename.endswith('.stl')
        sample_path=ROOT / 'tests' / 'test_concept.stl'
        sample.save_as(str(sample_path))
        page.locator('#stlFile').set_input_files(str(sample_path))
        assert page.get_by_role('button',name='Apply STL bounding dimensions to quote').count()==1
        assert page.locator('.viewer-wrap .viewer-tag').first.inner_text().startswith('STL REFERENCE')
        page.locator('#applyDimensions').click()
        with page.expect_download() as dl2:
            page.locator('#exportBtn').click()
        assert dl2.value.suggested_filename.endswith('.json')
        page.get_by_role('button',name='Route Optimizer').first.click()
        assert page.locator('.route-card').count()==3
        page.get_by_role('button',name='Model & Methods').first.click()
        assert '6.70%' in page.locator('#app').inner_text()
        page.get_by_role('button',name='3D Quote Studio').first.click()
        page.once('dialog',lambda d:d.accept('Test Scenario'))
        page.locator('#saveScenario').click()
        page.get_by_role('button',name='Scenario Portfolio').first.click()
        assert page.locator('.quote-card').count()==1
        with page.expect_download() as dl3:
            page.locator('#exportPortfolio').click()
        assert dl3.value.suggested_filename.endswith('.csv')
        page.locator('#guidedBtn').click()
        assert page.locator('#guided').is_visible()
        for _ in range(4):page.locator('#tourNext').click()
        assert '05 / 05' in page.locator('#tourStep').inner_text()
        page.locator('#tourExit').click()
        assert not errors,errors
        # mobile layout, test no missing headings
        mobile=browser.new_page(viewport={'width':390,'height':844}, device_scale_factor=1)
        mobile.set_content(html,wait_until='load')
        mobile.locator('#menu').click()
        assert 'open' in mobile.locator('#side').get_attribute('class')
        mobile.get_by_role('button',name='3D Quote Studio').first.click()
        assert mobile.locator('#partCanvas').count()==1
        mobile.screenshot(path=str(ROOT/'preview_2_mobile.png'), full_page=True)
        browser.close()
        sample_path.unlink(missing_ok=True)
        print('PASS: 3D viewer, batch recalculation, STL import, quote export, route optimizer, model labeling, scenario CSV, tour, mobile navigation')

if __name__ == '__main__':
    run_tests()
