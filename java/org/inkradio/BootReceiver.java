package org.inkradio;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import org.kivy.android.PythonActivity;

/**
 * 開機自動啟動 App：監聽 BOOT_COMPLETED，啟動 PythonActivity。
 * App 啟動後會讀取 prefs.json 的 autoplay 偏好，決定是否自動播放預設頻道。
 */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            Intent i = new Intent(context, PythonActivity.class);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(i);
        }
    }
}
