// Reflection shim for the user's own thinkorswim parser.
//
// This file contains no Schwab code. It calls the parser classes that already
// exist in the user's local installation, via reflection, so it compiles without
// needing those jars at build time.
//
// Output contract (parsed by tos_toolkit/parser/bridge.py):
//   RESULT: OK            -> grammatically valid
//   RESULT: FAIL          -> see following lines
//
// See docs/adr/0004-no-jar-redistribution.md.

import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Paths;

public final class Checker {

    private Checker() {}

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.out.println("RESULT: FAIL");
            System.out.println("usage: Checker <file>");
            return;
        }

        String content = new String(Files.readAllBytes(Paths.get(args[0])), "UTF-8");

        Class<?> parserClass = Class.forName(
            "com.devexperts.tos.thinkscript.ThinkScriptParser");

        Method doPlainParse = parserClass.getDeclaredMethod("doPlainParse", String.class);
        doPlainParse.setAccessible(true);
        Object result = doPlainParse.invoke(null, content);

        Method getErrors = result.getClass().getMethod("getErrors");
        getErrors.setAccessible(true);
        Object errors = getErrors.invoke(result);

        if (errors == null) {
            System.out.println("RESULT: OK");
            return;
        }

        int size = (int) errors.getClass().getMethod("size").invoke(errors);
        if (size == 0) {
            System.out.println("RESULT: OK");
            return;
        }

        System.out.println("RESULT: FAIL");
        System.out.println("errors: " + size);
        for (int i = 0; i < size; i++) {
            Object error = errors.getClass().getMethod("get", int.class).invoke(errors, i);
            System.out.println("  " + error);
        }
    }
}
