import Network
import XCTest

/// Drives the entry composer the way a finger does: pick a deck, add
/// a card, tap Save. Exists because "the Save button is broken" is a
/// UI-level symptom that unit tests on the sync engine can't see.
/// Runs against the `-seedComposerTest` fixtures (a "ZZ" deck, spread,
/// and profiles) with sync pointed at a dead local port, so saving
/// exercises the offline/outbox path without touching real data.
final class ComposerUITests: XCTestCase {

    private var app: XCUIApplication!

    /// A tar-pit standing in for an asleep Mac: accepts connections
    /// on the port the seeded app syncs to, then never replies. A
    /// save that waits on the network freezes against it for the
    /// full URLSession timeout — which is the bug these tests pin.
    private static let tarPit: NWListener? = {
        guard let listener = try? NWListener(using: .tcp, on: 5998) else {
            return nil
        }
        listener.newConnectionHandler = { connection in
            connection.start(queue: .global())
        }
        listener.start(queue: .global())
        return listener
    }()

    override func setUpWithError() throws {
        continueAfterFailure = false
        XCTAssertNotNil(Self.tarPit, "Could not start the tar-pit server")
        app = XCUIApplication()
        app.launchArguments = ["-seedComposerTest"]
        app.launch()
    }

    /// Enter the composer the way a person does: the Journal tab's
    /// "+" button — so dismissal on Save is the real presentation,
    /// not the debug deep-link.
    private func openComposer() -> XCUIElement {
        let compose = app.navigationBars["Journal"].buttons["New entry"]
        XCTAssertTrue(compose.waitForExistence(timeout: 10),
                      "Journal compose button never appeared")
        compose.tap()
        let navBar = app.navigationBars["New Entry"]
        XCTAssertTrue(navBar.waitForExistence(timeout: 10),
                      "Composer never appeared")
        return navBar
    }

    func testFreeformSaveDismissesQuickly() throws {
        let navBar = openComposer()

        let save = navBar.buttons["Save"]
        XCTAssertTrue(save.exists, "No Save button in the composer")
        XCTAssertFalse(save.isEnabled,
                       "Save should be disabled before any reading is valid")

        // Pick the deck (row label collapses to "Deck, Choose…").
        tapDeckRow()
        XCTAssertTrue(app.navigationBars["Deck"].waitForExistence(timeout: 5),
                      "Deck picker never appeared")
        let deckRow = app.buttons["ZZ UITest Deck"]
        XCTAssertTrue(deckRow.waitForExistence(timeout: 5),
                      "Seeded deck missing from the deck picker")
        deckRow.tap()

        // Freeform card: no spread, just "Add card".
        let addCard = app.buttons["Add card"]
        XCTAssertTrue(addCard.waitForExistence(timeout: 5),
                      "'Add card' row missing after choosing a deck")
        addCard.tap()
        XCTAssertTrue(
            app.navigationBars["Choose a card"].waitForExistence(timeout: 5),
            "Card picker never appeared")
        let cardRow = app.buttons["ZZ Card One"]
        XCTAssertTrue(cardRow.waitForExistence(timeout: 5),
                      "Seeded card missing from the card picker")
        cardRow.tap()

        // The picked card shows in the form and Save lights up.
        XCTAssertTrue(app.staticTexts["ZZ Card One"].waitForExistence(timeout: 5),
                      "Picked card not shown in the composer")
        XCTAssertTrue(save.waitForEnabled(timeout: 5),
                      "Save stayed disabled after a valid reading")

        // The core of the bug report: tapping Save must close the
        // composer promptly even when the Mac is unreachable.
        save.tap()
        let start = Date()
        let gone = navBar.waitForNonExistence(timeout: 15)
        let elapsed = Date().timeIntervalSince(start)
        XCTAssertTrue(gone, "Composer never dismissed after Save")
        XCTAssertLessThan(
            elapsed, 5,
            "Save took \(elapsed)s to dismiss — it must not wait on the network")
    }

    func testSpreadSlotsAndExtraCardSave() throws {
        let navBar = openComposer()
        let save = navBar.buttons["Save"]

        tapDeckRow()
        let deckRow = app.buttons["ZZ UITest Deck"]
        XCTAssertTrue(deckRow.waitForExistence(timeout: 5))
        deckRow.tap()

        // Choose the seeded three-card spread.
        let spreadRowButton = app.buttons["Spread, No spread"]
        XCTAssertTrue(spreadRowButton.waitForExistence(timeout: 5),
                      "Spread row not found. Hierarchy: \(app.debugDescription)")
        spreadRowButton.tap()
        let spreadRow = app.buttons["ZZ Three Card"]
        XCTAssertTrue(spreadRow.waitForExistence(timeout: 5),
                      "Seeded spread missing from the spread picker")
        spreadRow.tap()

        // Fill the first slot.
        let chooseCard = app.buttons["Choose card…"].firstMatch
        XCTAssertTrue(chooseCard.waitForExistence(timeout: 5),
                      "No empty slot rows after choosing a spread")
        chooseCard.tap()
        let cardRow = app.buttons["ZZ Card One"]
        XCTAssertTrue(cardRow.waitForExistence(timeout: 5))
        cardRow.tap()

        // Add an extra/clarifier card.
        let addExtra = app.buttons["Add extra card"]
        XCTAssertTrue(addExtra.waitForExistence(timeout: 5),
                      "'Add extra card' row missing in spread mode")
        addExtra.tap()
        let extraRow = app.buttons["ZZ Card Two"]
        XCTAssertTrue(extraRow.waitForExistence(timeout: 5))
        extraRow.tap()

        XCTAssertTrue(save.waitForEnabled(timeout: 5),
                      "Save stayed disabled after filling the spread")
        save.tap()
        XCTAssertTrue(navBar.waitForNonExistence(timeout: 15),
                      "Composer never dismissed after Save")
    }
}

private extension ComposerUITests {
    /// The composer's Deck picker row. Matched by its exact combined
    /// accessibility label — a loose BEGINSWITH 'Deck' predicate also
    /// catches the Decks tab behind the sheet.
    func tapDeckRow() {
        let row = app.buttons["Deck, Choose…"]
        if !row.waitForExistence(timeout: 5) {
            XCTFail("Deck row not found. Hierarchy: \(app.debugDescription)")
        }
        row.tap()
    }
}

private extension XCUIElement {
    func waitForEnabled(timeout: TimeInterval) -> Bool {
        let predicate = NSPredicate(format: "isEnabled == true")
        let expectation = XCTNSPredicateExpectation(
            predicate: predicate, object: self)
        return XCTWaiter().wait(for: [expectation], timeout: timeout) == .completed
    }

    func waitForNonExistence(timeout: TimeInterval) -> Bool {
        let predicate = NSPredicate(format: "exists == false")
        let expectation = XCTNSPredicateExpectation(
            predicate: predicate, object: self)
        return XCTWaiter().wait(for: [expectation], timeout: timeout) == .completed
    }
}
