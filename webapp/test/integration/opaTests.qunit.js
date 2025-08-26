/* global QUnit */
QUnit.config.autostart = false;

sap.ui.require(["sap/ai/orchestrator/test/integration/AllJourneys"
], function () {
	QUnit.start();
});
