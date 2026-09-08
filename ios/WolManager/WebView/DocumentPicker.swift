import UIKit
import UniformTypeIdentifiers

/*
 * Document-Picker (Import/Export) — iOS-Äquivalent zu SAF (ACTION_CREATE_DOCUMENT /
 * ACTION_OPEN_DOCUMENT). Export: Inhalt wird in eine temporäre Datei mit dem
 * vorgeschlagenen Namen geschrieben, der Export-Picker kopiert sie an den Zielort.
 * Der WebViewController hält einen starken Verweis auf das Delegate, bis der
 * Picker geschlossen wird.
 */
final class DocumentPicker: NSObject, UIDocumentPickerDelegate {

    private var onPicked: ((URL?) -> Void)?
    private var onExported: ((Bool) -> Void)?
    private var picker: UIDocumentPickerViewController?
    weak var presenter: UIViewController?

    /// Dokument anlegen (Export): Data → tmp-Datei → Export-Picker (Benutzer wählt Ort).
    func exportDocument(suggestedName: String, data: Data, completion: @escaping (Bool) -> Void) {
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent(suggestedName)
        do {
            try data.write(to: tmp)
        } catch {
            completion(false)
            return
        }
        let picker = UIDocumentPickerViewController(forExporting: [tmp], asCopy: true)
        self.onExported = completion
        self.picker = picker
        picker.delegate = self
        presenter?.present(picker, animated: true)
    }

    /// Bestehendes Dokument öffnen (Import).
    func openDocument(completion: @escaping (URL?) -> Void) {
        var types: [UTType] = [.json, .plainText]
        if let csv = UTType(filenameExtension: "csv") { types.insert(csv, at: 0) }
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: types, asCopy: true)
        self.onPicked = completion
        self.picker = picker
        picker.delegate = self
        presenter?.present(picker, animated: true)
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        if onExported != nil {
            let cb = onExported
            cleanup()
            cb?(true)
        } else {
            let cb = onPicked
            cleanup()
            cb?(urls.first)
        }
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        if onExported != nil {
            let cb = onExported
            cleanup()
            cb?(false)
        } else {
            let cb = onPicked
            cleanup()
            cb?(nil)
        }
    }

    private func cleanup() {
        onPicked = nil
        onExported = nil
        picker = nil
    }
}
